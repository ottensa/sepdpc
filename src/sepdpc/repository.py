from pathlib import Path
from typing import Optional, List, Callable, Union, Any

import yaml
from adastra.client import SepClient
from adastra.sep.models import (
    Column,
    DefinitionProperties,
    Owner,
    Link,
    SampleQuery,
    Domain,
    DataProduct,
    View,
    MaterializedView,
    Tag
)
from adastra.sep.services.data_product_service import DataProductService
from deepdiff import DeepDiff
from pydantic import BaseModel, Field, AliasChoices, field_validator

_DESIRED_METADATA_ORDER = ['catalog', 'domain', 'name', 'summary', 'owner', 'links', 'tags']


class InterstellarBaseModel(BaseModel):
    @field_validator('*')
    def empty_to_none(cls, v):
        if isinstance(v, (str, dict, list, set)) and not v:
            v = None

        return v


class DomainStruct(InterstellarBaseModel):
    id: Optional[str] = None
    name: str
    desc: Optional[str] = Field(default=None, validation_alias=AliasChoices('desc', 'description'))
    path: Optional[str] = Field(default=None, validation_alias=AliasChoices('path', 'schemaLocation'))


class DatasetStruct(InterstellarBaseModel):
    name: str
    query: str
    summary: Optional[str] = None
    columns: Optional[List[Column]] = None
    materialization: Optional[DefinitionProperties] = None


class ProductStruct(InterstellarBaseModel):
    id: Optional[str] = None
    name: str
    desc: str
    summary: str
    catalog: str
    domain: str
    owner: list[Owner]
    links: Optional[list[Link]] = None
    tags: Optional[list[str]] = None
    samples: Optional[list[SampleQuery]] = None
    datasets: list[DatasetStruct] = None


class RepositoryDiff(BaseModel):
    deleted_domains: List[DomainStruct]
    created_domains: List[DomainStruct]
    updated_domains: List[DomainStruct]
    deleted_products: List[ProductStruct]
    created_products: List[ProductStruct]
    updated_products: List[ProductStruct]
    reassigned_products: List[ProductStruct]


class Repository(BaseModel):
    domains: List[DomainStruct]
    products: List[ProductStruct]


def from_server(server_client: SepClient) -> Repository:
    """Laden der Domains und der Produkte von SEP und in die Repository Struktur bringen"""
    dpc = server_client.data_product_service()
    dc = server_client.domain_service()

    sep_domains = dc.list()
    sep_products = dpc.list()

    domains = [DomainStruct(**domain.model_dump()) for domain in sep_domains]
    products = []

    for dp in sep_products:
        tags = dpc.get_tags(dp.id)
        samples = dpc.get_samples(dp.id)
        datasets = []
        for view in dp.views:
            datasets.append(
                DatasetStruct(
                    name=view.name,
                    query=view.definitionQuery,
                    summary=view.description,
                    columns=view.columns
                )
            )

        for view in dp.materializedViews:
            datasets.append(
                DatasetStruct(
                    name=view.name,
                    query=view.definitionQuery,
                    summary=view.description,
                    columns=view.columns,
                    materialization=view.definitionProperties
                )
            )

        product = ProductStruct(
            id=dp.id,
            name=dp.name,
            desc=dp.description,
            summary=dp.summary,
            catalog=dp.catalogName,
            domain=next(d.name for d in domains if d.id == dp.dataDomainId),
            owner=dp.owners,
            links=dp.relevantLinks,
            tags=[tag.value for tag in tags],
            samples=samples,
            datasets=datasets
        )
        products.append(product)

    return Repository(domains=domains, products=products)


def _load_domains_yaml(path: Path) -> List[DomainStruct]:
    domains_yaml_path = path / 'domains.yaml'
    domains_yaml = yaml.safe_load(domains_yaml_path.read_text(encoding="utf-8"))
    domains = [DomainStruct(**domain) for domain in domains_yaml]
    return domains


def _load_dataset_definition(datasets_path: Path, dataset: str) -> DatasetStruct:
    dataset_path = datasets_path / f'{dataset}.sql'

    dataset_definition = {
        'name': dataset,
        'query': dataset_path.read_text(encoding='utf-8')
    }

    dataset_metadata_path = datasets_path / f'{dataset}.yaml'
    if dataset_metadata_path.exists():
        metadata = yaml.safe_load(dataset_metadata_path.read_text(encoding='utf-8'))
        dataset_definition.update(metadata)

    return DatasetStruct(**dataset_definition)


def _load_sample(sample_path: Path) -> SampleQuery:
    name = sample_path.stem
    query = sample_path.read_text(encoding='utf-8')
    return SampleQuery(name=name, query=query)


def _load_product_definition(path: Path) -> ProductStruct:
    metadata_yaml_path = path / 'metadata.yaml'
    metadata = yaml.safe_load(metadata_yaml_path.read_text(encoding="utf-8"))

    readme_md_path = path / 'readme.md'
    metadata['desc'] = readme_md_path.read_text(encoding='utf-8')

    datasets_path = path / 'datasets'
    dataset_names = {ds.stem for ds in datasets_path.iterdir() if ds.is_file()}
    metadata['datasets'] = [_load_dataset_definition(datasets_path, dataset) for dataset in dataset_names]

    samples_path = path / 'samples'
    if samples_path.exists():
        metadata['samples'] = [_load_sample(sample_path) for sample_path in samples_path.iterdir()]

    return ProductStruct(**metadata)


def from_local(path: str) -> Repository:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError('The repository directory does not exist')

    domains = _load_domains_yaml(path)
    products = [_load_product_definition(product_path) for product_path in path.iterdir()
                if product_path.is_dir() and not product_path.name.startswith('.')]

    return Repository(domains=domains, products=products)


def validate(repo: Repository) -> bool:
    # Validate uniqueness of domain names
    domain_names = [domain.name for domain in repo.domains]
    unique_domain_names = set(domain_names)
    if len(unique_domain_names) != len(domain_names):
        raise SyntaxError("Domain Names must be unique")

    # Validate that domains used in data products are actually defined
    product_domains = set([product.domain for product in repo.products])
    if not product_domains.issubset(unique_domain_names):
        raise SyntaxError('Domains used in a Data Product must be defined in domains.yaml')

    # Validate uniqueness of product names
    product_names = [product.name for product in repo.products]
    unique_product_names = set(product_names)
    if len(unique_product_names) != len(product_names):
        raise SyntaxError("Product Names must be unique")

    return True


def _calculate_deleted_or_created_entities(entities1: List[Union[DomainStruct, ProductStruct]],
                                           entities2: List[Union[DomainStruct, ProductStruct]]):
    # deleted_domains = [d for d in repo1.domains if d.name not in [dn.name for dn in repo2.domains]]
    deleted = [e1 for e1 in entities1 if e1.name not in [e2.name for e2 in entities2]]
    created = [e2 for e2 in entities2 if e2.name not in [e1.name for e1 in entities1]]

    return deleted, created


def _calculate_changes(entities1: List[Union[DomainStruct, ProductStruct]],
                       entities2: List[Union[DomainStruct, ProductStruct]],
                       cls: Callable[[Any], Union[DomainStruct, ProductStruct]]):
    updated = []
    reassigned = []

    deleted, created = _calculate_deleted_or_created_entities(entities1, entities2)
    update_candidates = (
        sorted([e1 for e1 in entities1 if e1.name not in [d.name for d in deleted]], key=lambda el: el.name),
        sorted([e2 for e2 in entities2 if e2.name not in [c.name for c in created]], key=lambda el: el.name),
    )

    if len(update_candidates[0]) != len(update_candidates[1]):
        raise SyntaxError('Something went wrong')

    for idx in range(len(update_candidates[0])):
        d1 = update_candidates[0][idx].model_dump(exclude_none=True)
        d2 = update_candidates[1][idx].model_dump(exclude_none=True)

        if d1['name'] != d2['name']:
            raise SyntaxError('Something went wrong')

        ddiff = DeepDiff(d1, d2, exclude_paths='id', ignore_order=True)
        if ddiff:
            d1.update(d2)
            if 'domain' in ddiff.affected_root_keys:
                reassigned.append(cls(**d1))
                if len(ddiff.affected_root_keys) > 1:
                    updated.append(cls(**d1))
            else:
                updated.append(cls(**d1))

    return deleted, created, updated, reassigned


def diff(repo1: Repository, repo2: Repository):
    """Unterschiede rausrechnen"""
    validate(repo1)
    validate(repo2)

    domain_changes = _calculate_changes(repo1.domains, repo2.domains, DomainStruct)
    product_changes = _calculate_changes(repo1.products, repo2.products, ProductStruct)

    return RepositoryDiff(
        deleted_domains=domain_changes[0],
        created_domains=domain_changes[1],
        updated_domains=domain_changes[2],
        deleted_products=product_changes[0],
        created_products=product_changes[1],
        updated_products=product_changes[2],
        reassigned_products=product_changes[3],
    )


def _persist_domains_yaml(path: Path, domains: List[DomainStruct]):
    # domains = [DomainStruct(name=d.name, desc=d.desc, path=d.path).model_dump(exclude_none=True) for d in domains]
    domains = [d.model_dump(exclude_none=True, exclude={'id'}) for d in domains]
    domains_yaml = path / "domains.yaml"
    with domains_yaml.open('w', encoding='utf-8') as f:
        yaml.dump(domains, f, sort_keys=False)


def _persist_datasets(path: Path, datasets: List[DatasetStruct]):
    if datasets:
        ds_path = path / 'datasets'
        ds_path.mkdir()

        for dataset in datasets:
            dataset_path = ds_path / f'{dataset.name}.sql'
            dataset_path.write_text(dataset.query, encoding='utf-8')

            dataset_metadata = dataset.model_dump(exclude_none=True, exclude={'name', 'query'})
            if dataset_metadata:
                dataset_metadata_path = ds_path / f'{dataset.name}.yaml'
                with dataset_metadata_path.open('w', encoding='utf-8') as f:
                    yaml.dump(dataset_metadata, f, sort_keys=False)


def _persist_samples(path: Path, samples: List[SampleQuery]):
    if samples:
        s_path = path / 'samples'
        s_path.mkdir()

        for sample in samples:
            sample_path = s_path / f'{sample.name}.sql'
            sample_path.write_text(sample.query, encoding='utf-8')


def _persist_data_product(path: Path, data_product: ProductStruct):
    dp_path = path / data_product.name.lower().replace(' ', '-')
    dp_path.mkdir()

    metadata_path = dp_path / "metadata.yaml"
    with metadata_path.open('w', encoding='utf-8') as f:
        metadata = data_product.model_dump(exclude_none=True, exclude={'id', 'desc', 'samples', 'datasets'})
        metadata = {k: metadata[k] for k in _DESIRED_METADATA_ORDER if k in metadata}
        yaml.dump(metadata, f, sort_keys=False)

    readme_path = dp_path / "readme.md"
    readme_path.write_text(data_product.desc, encoding='utf-8')

    _persist_datasets(dp_path, data_product.datasets)
    _persist_samples(dp_path, data_product.samples)


def persist(repo: Repository, path: str):
    """Ins Dateisystem schreiben"""
    validate(repo)
    path = Path(path)
    path.mkdir()

    _persist_domains_yaml(path, repo.domains)

    for data_product in repo.products:
        _persist_data_product(path, data_product)


def _product_struct_to_data_product(product_struct: ProductStruct, domain_id: str) -> DataProduct:
    data_product = DataProduct(id=product_struct.id,
                               name=product_struct.name,
                               catalogName=product_struct.catalog,
                               dataDomainId=domain_id,
                               summary=product_struct.summary,
                               description=product_struct.desc,
                               owners=product_struct.owner,
                               relevantLinks=product_struct.links)

    dp_view = []
    dp_mat_view = []
    for ds in product_struct.datasets:
        if not ds.materialization:
            dp_view.append(View(name=ds.name,
                                description=ds.summary,
                                definitionQuery=ds.query,
                                columns=ds.columns))
        else:
            dp_mat_view.append(MaterializedView(name=ds.name,
                                                description=ds.summary,
                                                definitionQuery=ds.query,
                                                columns=ds.columns,
                                                definitionProperties=ds.materialization))

    data_product.views = dp_view if dp_view else None
    data_product.materializedViews = dp_mat_view if dp_mat_view else None

    return data_product


def _upsert_data_product(dpc: DataProductService, product_struct: ProductStruct, domain_id: str,
                         upsert: Callable[[DataProduct], DataProduct]):
    data_product = _product_struct_to_data_product(product_struct, domain_id)

    data_product = upsert(data_product)

    if product_struct.tags:
        tags = [Tag(value=t) for t in product_struct.tags]
        dpc.set_tags(data_product.id, tags)

    if product_struct.samples:
        samples = [SampleQuery(name=s.name, query=s.query) for s in product_struct.samples]
        dpc.set_samples(data_product.id, samples)

    dpc.publish(data_product.id)


def publish(server_client: SepClient, repo: Repository):
    """Auf den Server schieben"""
    validate(repo)
    remote_repo = from_server(server_client)

    # mapping von domain name auf domain id
    domain_mapping = dict([(domain.name, domain.id) for domain in remote_repo.domains])

    dpc = server_client.data_product_service()
    dc = server_client.domain_service()

    delta = diff(remote_repo, repo)
    # 1. delete products
    for dp in delta.deleted_products:
        dpc.delete(dp.id)

    # 2. create domains
    for d in delta.created_domains:
        domain_to_create = Domain(name=d.name, description=d.desc, schemaLocation=d.path)
        new_domain = dc.create(domain_to_create)
        domain_mapping[new_domain.name] = new_domain.id

    # 3. reassign products
    for dp in delta.reassigned_products:
        dpc.reassign(dp.id, domain_mapping[dp.domain])

    # 4. delete domains
    for d in delta.deleted_domains:
        dc.delete(d.id)

    # 5. update products
    for dp in delta.updated_products:
        _upsert_data_product(dpc, dp, domain_mapping[dp.domain], dpc.update)

    # 6. update domains
    for d in delta.updated_domains:
        dc.update(Domain(id=d.id, name=d.name, description=d.desc, schemaLocation=d.path))

    # 7. create products
    for dp in delta.created_products:
        _upsert_data_product(dpc, dp, domain_mapping[dp.domain], dpc.create)
