# Troubleshooting

This article contains troubleshooting steps for known issues. If you encounter any problems
with the application not addressed here, check the [GitHub Issues](https://github.com/open-edge-platform/edge-ai-suites/issues)
board. Feel free to file new tickets there (after learning about the guidelines for [Contributing](https://github.com/open-edge-platform/edge-ai-suites/blob/main/CONTRIBUTING.md)).

## 1. Seeing "No Data" in Grafana

**Issue**

Grafana panels show **"No Data"** even though the container/stack is
running.

**Reason**

The **system date/time is incorrect** on the device. If the system time
is wrong, data timestamps fall outside Grafana's query window.

**Solution**

Check the date/time using the command below:

``` sh
date
```

Set the correct date/time manually:

``` sh
sudo date -s 'YYYY-MM-DD HH:MM:SS'
```

Set date/time from the internet:

``` sh
sudo date -s "$(wget --method=HEAD -qSO- --max-redirect=0 google.com 2>&1 | sed -n 's/^ *Date: *//p')"
```

---

## 2. Influx -- Data Being Deleted Beyond Retention Policy (RP)

**Issue**

- Data appears to be deleted beyond the configured retention policy (RP).
- InfluxDB 1.x deletes old data based on the retention policy duration
  and shard group duration.

**Reason**

- Data is grouped into **shards**.
- Shards are deleted only when **all data inside them** is older than
  the RP.
- For RPs **≤ 2 days**, shard group duration = **1 hour**.
- InfluxDB always expires data at **RP + shard duration**.

Example:

For a **1-hour RP**: - Data written at **00:00** goes into the shard
covering **00:00--01:00**. - The shard closes at **01:00**. - InfluxDB
deletes the shard only when everything inside it is past the RP → at
**02:00**.

So the effective expiration time is **1 hour RP + 1 hour shard duration
= 2 hours**.

| Retention Policy | Shard Duration |Actual Expiry |
|---|---|---|
| 1 hour | 1 hour | 2 hours |
| 2 days | 1 hour | 2 days + 1 hr |
| 30 days | 24 hours | 30 days + 24 hr |

**Solution**

- Understand that this is **normal and expected behavior** in InfluxDB
    1.x.
- A 1-hour RP will **always** result in \~2 hours before deletion.
- No configuration can force deletion exactly at the RP limit.

---

## 3. Time Series Analytics Microservice (Docker/Helm) -- Takes Time to Start or Shows Python Packages Installing

**Issue**

The Time Series Analytics Microservice takes time to start or displays
messages about Python packages being installed.

**Reason**

UDF packages require several dependent packages to be installed during
runtime, as specified under `udfs/requirements.txt`. Once these
dependencies are installed, the **Time Series Analytics** microservice
initializes and starts inferencing.

**Solution**

No action required --- wait for the **time-series-analytics**
microservice to complete downloading the dependent packages and
initialize Kapacitor to start inference.

---

## 4. Helm Deployment -- Grafana Doesn't Load or Shows `502 Bad Gateway`

**Issue**

Grafana UI fails to load after a Helm deployment, showing a **502 Bad
Gateway** error or taking more than 2 minutes to load.

**Reason**

Helm deployment takes time to initialize Grafana containers. During
this period, the ingress/service may route requests before the pods are
fully ready.

**Solution**

No action required --- wait for the deployment to complete and for all pods to become ready.
