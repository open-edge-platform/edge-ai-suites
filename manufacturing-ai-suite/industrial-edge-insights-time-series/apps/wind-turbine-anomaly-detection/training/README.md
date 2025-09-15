## Building the models for inference usage in the User Defined Functions of Time Series Analytics Microservice

The wind turbine anomaly model is built with the
jupyter notebook at [windturbine_anomaly_detection.ipynb](windturbine_anomaly_detection.ipynb) and the dataset [T1.csv](T1.csv) used is coming from https://www.kaggle.com/datasets/berkerisen/wind-turbine-scada-dataset.

Launch the jupyter notebook from browser and run the notebook by following below steps in the terminal, tweak the port config if there is any conflict:

```bash
# Assuming the repo is already cloned
# 1. Install dependent python packages
cd edge-ai-suites/manufacturing-ai-suite/wind-turbine-anomaly-detection/training
python3 -m venv ~/windturbine_venv
source ~/windturbine_venv/bin/activate
pip3 install -r requirements.txt
# 2. Launch jupyter notebook from the URL shown in the output of the below command (re-run this command if you see any kernel
# doesn't exist errors). Please provide the token in the browser if asked for, it can be fetched from the terminal where the 
# below command is getting executed
jupyter-notebook --ip=0.0.0.0 --port=8889 --no-browser
# 3. Open the below notebook from chrome browser, please don't miss to update the system_ip in the URL
http://<system_ip>:8889/doc/tree/windturbine_anomaly_detection.ipynb
```
