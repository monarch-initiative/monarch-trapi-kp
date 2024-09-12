# Developer Notes

These notes are only of interest to developers maintaining this repository.

## Maintaining Dependencies

This project uses the [poetry dependency management](https://python-poetry.org) tool to orchestrate its installation and dependencies. As such, new or revised Python module dependencies are curated within the **pyproject.toml** file.

For release step #5 below, you may need to install the 'export' poetry plug-in as follows:

```shell
poetry self add poetry-plugin-export
```

Then disable the plugin warning:

```shell
poetry config warnings.export false
```

## Project Releases

Steps to properly issue a new project release:

1. Run the unit test suite to ensure that nothing fails. Iterate to fix failures (in the code or in terms of revised unit tests to reflect fresh code designs)
2. Document release changes in the **CHANGELOG.md**
3. Update the **`[Tool Poetry]version =`** field in the **pyprojects.yaml**, e.g. "0.1.2"
4. Run **`poetry update`** (preferably, within a **`poetry shell`**)
5. The project pip **requirements.txt** file snapshot of dependencies should also be updated at this point (type **`$ poetry export --output requirements.txt`**, assuming that the [proper poetry export plugin is installed](https://python-poetry.org/docs/pre-commit-hooks#poetry-export)). This may facilitate module deployment within environments that prefer to use pip rather than poetry to manage their deployments.
6. Commit or pull request merge all files (including the **poetry.lock** file) to the local **main** branch.
7. Add the equivalent Git **tag** to **main**. This should be the Semantic Version string from step 4 with an added 'v' prefix, e.g. "v0.1.2".
8. Push **main** to remote.
9. Check if Git Actions for testing and documentation complete successfully.
10. Create a Git package release using the same release tag, e.g. "v0.1.2".
11. Check if Git Actions for package deployment is successful and check if the new version (e.g. "v0.1.2") is now visible on **[pypy.org](https://pypi.org/search/?q=OneHopTests)**
