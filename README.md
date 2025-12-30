# trobz_local


Local is a CLI tool to streamline Odoo development environments.
It automates repository management, directory structures, and virtual environments using `uv` and `odoo-venv`.

![Demo](./assets/demo.gif)


## Installation

With [`uv`](https://docs.astral.sh/uv/):

```bash
uv tool install git+ssh://git@github.com:trobz/local.py.git
```

### Getting Started

The first step is to initialize the directory structure for your local environment:

```bash
tlc init
```

*   `tlc pull-repos`: Clone or update Odoo and OCA repositories.
    *   **Filtering**: You can filter specific repositories using the `-f` or `--filter` flag.
        ```bash
        tlc pull-repos -f odoo -f web
        ```
*   `tlc create-venvs`: Create virtual environments for your Odoo versions.
*   `tlc install-tools`: Install other CLI tools defined in your config.
*   `tlc install-packages`: Install required system packages.

### Configuration

You can configure the tool using environment variables:

*   `NEWCOMER_MODE`: Set to `false` or `0` to disable interactive confirmations and help messages for a faster workflow.

Run `tlc --help` for more information on all commands.
