<p align="center">
    <img height="100" alt="sepdpc" src="https://github.com/ottensa/sepdpc/blob/main/docs/logo.png?raw=true" />
    <br>
    <i align="center">Manage Starburst Enterprise Data Products in a local Repository</i>
</p>

### Disclaimer
This is not part of the core Starburst product and is not covered by Starburst support agreements. 
It is a community developed set of scripts to make your life easier when managing Starburst Enterprise  Data Products.

## Introduction
This Python package is a CLI for managing Starburst Enterprise Data Products in a local repository.

The motivation behind this project comes from the demand I see at customers to manage Starburst Enterprise Data Products in git.

## Installation
Releases are not yet available on PyPI, but you can install using pip nonetheless:

```shell
python -m pip install -U pip
python -m pip install -U pip install git+https://github.com/ottensa/sepdpc.git
```

## Usage
*sepdpc* is a command line application that lets you manage your data products. 
The application has several subcommands that are described below.

```shell
$ sepdpc --help
                                                                                                                        
 Usage: sepdpc [OPTIONS] COMMAND [ARGS]...                                                                              
                                                                                                                        
╭─ Options ─────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.   │
│ --show-completion             Show completion for the current shell,      │
│                               to copy it or customize the installation.   │
│ --help                        Show this message and exit.                 │
╰───────────────────────────────────────────────────────────────────────────╯
╭─ Commands ────────────────────────────────────────────────────────────────╮
│ configure                                                                 │
│ diff                                                                      │
│ generate                                                                  │
│ publish                                                                   │
│ validate                                                                  │
╰───────────────────────────────────────────────────────────────────────────╯
```

### configure
In order to interact with your SEP Cluster, you need to tell the application where to find it and how to authenticate against ist.
You can either provide this information with every call using th `--host`, `--user` and `--token` options or run `sepdpc configure` to store this information in a config file.

```shell
$ sepdpc configure --help
                                                                                                                        
 Usage: sepdpc configure [OPTIONS]                                                                                      
                                                                                                                        
╭─ Options ─────────────────────────────────────────────────────────────────╮
│ *  --host         TEXT  The host of your Starburst Enterprise instance,   │
│                         e.g. https://sep.example.com:8443                 │
│                         [default: None]                                   │
│                         [required]                                        │
│ *  --user         TEXT  The username you are authenticating with          │ 
│                         [default: None]                                   │
│                         [required]                                        │
│ *  --token        TEXT  The token used for authentication                 │
│                         [default: None]                                   │
│                         [required]                                        │
│    --help               Show this message and exit.                       │
╰───────────────────────────────────────────────────────────────────────────╯
```

You can either provide the information using the options or run `sepdpc configure` without options and you will then be asked to provide it interactively.

### diff
If you have Data Products in your SEP Cluster as well as in a repository, you can run `sepdpc diff <path_to_repo>` to compare them and list the differences.

```shell
sepdpc diff --help     
                                                                                                                        
 Usage: sepdpc diff [OPTIONS] PATH                                                                                      
                                                                                                                        
╭─ Arguments ───────────────────────────────────────────────────────────────╮
│ *    path      TEXT  [default: None] [required]                           │
╰───────────────────────────────────────────────────────────────────────────╯
```

### generate
If you already have Data Products in you SEP Cluster and want to create a repository from those, you can run `sepdpc generate <path_to_repo>`.
It will download the Data Products and persist them into the given path.

```shell
sepdpc generate --help     
                                                                                                                        
 Usage: sepdpc diff [OPTIONS] PATH                                                                                      
                                                                                                                        
╭─ Arguments ───────────────────────────────────────────────────────────────╮
│ *    path      TEXT  [default: None] [required]                           │
╰───────────────────────────────────────────────────────────────────────────╯
```

### publish
In order to role you Data Products out to your SEP Cluster, you can run `sepdpc publish <path_to_repo>`.
It will take the Data Product Definitions stored in the given path and publish them to the SEP Cluster.
It will delete Data Products that are not reflected in the repository, create new Data Products and update changed ones.

```shell
sepdpc publish --help     
                                                                                                                        
 Usage: sepdpc diff [OPTIONS] PATH                                                                                      
                                                                                                                        
╭─ Arguments ───────────────────────────────────────────────────────────────╮
│ *    path      TEXT  [default: None] [required]                           │
╰───────────────────────────────────────────────────────────────────────────╯
```

### validate
In order to verify that your Data Product Definitions are correct, you can run `sepdpc validate <path_to_repo>`.
It will go through all definitions in the given repository and informs you about issues.
The validation will also be implicitly called before you try to publish your repository.

```shell
sepdpc validate --help     
                                                                                                                        
 Usage: sepdpc diff [OPTIONS] PATH                                                                                      
                                                                                                                        
╭─ Arguments ───────────────────────────────────────────────────────────────╮
│ *    path      TEXT  [default: None] [required]                           │
╰───────────────────────────────────────────────────────────────────────────╯
```

## Known issues and limitations
- This package does not claim to be complete and currently only focuses on Data Products
- It is an opinionated implementation and might behave differently that SEP itself
- Data Products that are not published or have unpublished changes may not successfully persist into local storage
- Only tested against Basic Authentication so far

## Contributing
Contributions are what make the open source community such an amazing place to learn, inspire, and create. 
Any contributions you make are greatly appreciated.

If you have a suggestion that would make this better, please fork the repo and create a pull request. 
You can also simply open an issue with the tag "enhancement". 
Don't forget to give the project a star! Thanks again!

## License
Distributed under the MIT License. See LICENSE for more information.
