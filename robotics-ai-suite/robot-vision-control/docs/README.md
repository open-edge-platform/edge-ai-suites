# Robotic Vision & Control [RVC] Documentation

This directpry contains the **Robotic Vision & Control [RVC]** system documentation, which is built from source using [Sphinx](https://www.sphinx-doc.org/). The following instructions will guide you through setting up the environment, installing dependencies, and building the HTML documentation.

---

## 1. Install System Dependencies

Before setting up the Python environment, ensure that essential system packages are installed. These packages include:

* `python3-pip` – for installing Python packages
* `graphviz` – for rendering diagrams in Sphinx
* `libenchant-2-dev` – required by spelling check extensions


```bash
sudo apt update
sudo apt install python3-pip
sudo apt install graphviz libenchant-2-dev
```

---

## 2. Set Up a Python Virtual Environment

Though not necessary, it is recommended to use a virtual environment to keep dependencies isolated.

```bash
# Navigate to the documentation folder
export DOCS_DIR=<path to edge-ai-suites folder>
cd $DOCS_DIR/edge-ai-suites/robotics-ai-suite/robot-vision-control/docs

# Create a new virtual environment
python3 -m venv venv_robotics-ai-suite-docs

# Activate the virtual environment
source venv_robotics-ai-suite-docs/bin/activate
```

---

## 3. Upgrade pip, setuptools, and wheel

Inside the virtual environment, upgrade core Python packaging tools. This ensures compatibility with modern packages.

```bash
pip install --upgrade pip setuptools wheel
```

---

## 4. Install Python Dependencies

With the virtual environment active, install all Python dependencies required to build the documentation:

```bash
pip install -r requirements.txt
```

Now reactivate the virtual environment:

```bash
source venv_robotics-ai-suite-docs/bin/activate
```

---

## 5. Build HTML Documentation

Once dependencies are installed and the virtual environment is active, generate the HTML version of the documentation:

```bash
make html
```

The output will be available in the `build/html` folder inside your `docs` directory. You can open the `index.html` file in a browser to view the documentation.

---