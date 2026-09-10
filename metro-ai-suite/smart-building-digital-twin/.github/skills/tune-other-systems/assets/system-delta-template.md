# Cross-System Tuning Checklist

## Machine
- Hostname:
- OS / kernel:
- CPU / platform generation:
- Intel GPU present: yes / no
- Proxy variables set (`HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`):

## Repo State
- Branch / commit:
- Fresh clone or reused workspace:
- `.env` copied from another machine: yes / no

## Key Environment Values
- `PUBLIC_HOSTNAME=`
- `API_BASE_URL=`
- `SCENESCAPE_UI_URL=`
- `DASHBOARD_URL=`
- `DETECTION_DEVICE=`
- `INFERENCE_DEVICE=`
- `SCENE_ID=`

## Service State
- `docker compose ps` summary:
- Unhealthy or restarting services:
- Relevant logs checked:

## Scene Wiring
- Imported scene name:
- `config/resolved-uuids.json` present: yes / no
- Scene UUID matches live API: yes / no
- Regulated MQTT topic verified: yes / no

## Behavior Delta
- What differs from the reference system:
- Repro steps:
- Suspected layer: setup / environment / scene config / analytics logic
- Suspected performance effect: inference cadence / replay timing / event ordering / threshold crossing / unknown

## Durable Fix
- Repo files changed:
- Exported config updated: yes / no
- Follow-up validation needed:
