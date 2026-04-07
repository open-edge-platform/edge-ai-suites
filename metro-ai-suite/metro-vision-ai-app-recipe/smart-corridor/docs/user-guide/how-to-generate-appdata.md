# How to Generate Appdata tar file

This guide explains how to regenerate a SceneScape appdata archive (for example `smart-corridor-ri.tar.bz2`) from a running environment.

## Scope

- Environment: `metro-ai-suite/metro-vision-ai-app-recipe`
- Web container: `metro-vision-ai-app-recipe-web-1`
- DB container: `metro-vision-ai-app-recipe-pgserver-1`

## Prerequisites

1. Docker commands must work for your user.
2. The SceneScape stack must be running.

## 1) Create Patch File On Host (`/tmp/save_db.patch`)

Create a file named save_db.patch in /tmp.

Paste the content below, then save it.

```diff
diff --git a/tmp/requirements-runtime.txt b/tmp/requirements-runtime.txt
--- a/tmp/requirements-runtime.txt
+++ b/tmp/requirements-runtime.txt
@@ -24,4 +24,5 @@
 scipy==1.16.3
 trimesh==4.11.2
 urllib3==2.6.3
 websockets==15.0.1
+django-archive
diff --git a/home/scenescape/SceneScape/manager/settings.py b/home/scenescape/SceneScape/manager/settings.py
--- a/home/scenescape/SceneScape/manager/settings.py
+++ b/home/scenescape/SceneScape/manager/settings.py
@@ -31,6 +31,7 @@ INSTALLED_APPS = [
   'django.contrib.sessions',
   'django.contrib.messages',
   'django.contrib.staticfiles',
+  'django_archive',
   'rest_framework',
   'rest_framework.authtoken',
   'axes',
```

Optional quick validation:

```bash
ls -lh /tmp/save_db.patch
grep -n "django-archive\|django_archive" /tmp/save_db.patch
```

## 2) Copy Patch Into Web Container

```bash
cd '<local-path>'/edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe
sg docker -c "docker cp /tmp/save_db.patch metro-vision-ai-app-recipe-web-1:/tmp/save_db.patch"
```

## 3) Apply Patch In Container As Root

Important: patch must run as root because `/tmp/requirements-runtime.txt` is root-owned.

```bash
sg docker -c "docker exec -it -u 0 metro-vision-ai-app-recipe-web-1 bash"
apt-get update && apt-get install -y patch
pip install django-archive
patch -p1 < /tmp/save_db.patch
```

Expected output should include both files being patched. See example below:
```bash
root@7e6d608f1613:/# patch -p1 < /tmp/save_db.patch
patching file tmp/requirements-runtime.txt
patching file home/scenescape/SceneScape/manager/settings.py
patch unexpectedly ends in middle of line
Hunk #1 succeeded at 31 with fuzz 1.
```

## 4) Run Archive Command From Correct Directory

Run from `/home/scenescape/SceneScape` and do not redirect stdout to tar.

```bash
cd /home/scenescape/SceneScape
DBHOST=metro-vision-ai-app-recipe-pgserver-1 python manage.py archive
```

Verify output archive exists (usually `<date>-<time>.tar.bz2` in current directory):

```bash
ls -lh /home/scenescape/SceneScape/*.tar.bz2
tar -tjf /home/scenescape/SceneScape/'<date>-<time>'.tar.bz2 | head
```

## 5) Copy Archive To Host Temp Area

Exit container if needed, then run on host:

```bash
cd edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe
mkdir -p /tmp/dbexport
sg docker -c "docker cp metro-vision-ai-app-recipe-web-1:/home/scenescape/SceneScape/'<date>-<time>'.tar.bz2 /tmp/dbexport/'<date>-<time>'.tar.bz2"
```

## 6) Extract Archive

```bash
mkdir -p /tmp/dbexport/work
sudo apt-get install -y bzip2 && tar -xjf /tmp/dbexport/'<date>-<time>'.tar.bz2 -C /tmp/dbexport/work
ls -lh /tmp/dbexport/work
```

## 7) Remove Sensitive Auth Records From `data.json`

```bash
python3 - <<'PY'
import json
from pathlib import Path

p = Path('/tmp/dbexport/work/data.json')
data = json.loads(p.read_text())

drop_models = {
    'auth.user',
    'authtoken.token',
    'axes.accesslog',
    'manager.pubsubacl',
    'manager.usersession',
}

clean = [row for row in data if row.get('model') not in drop_models]
print(f'before={len(data)} after={len(clean)} removed={len(data)-len(clean)}')
p.write_text(json.dumps(clean, separators=(',', ':')))
PY
```

## 8) Repack Final Appdata Tar

```bash
cd /tmp/dbexport/work
tar -cjf /tmp/dbexport/smart-corridor-ri.tar.bz2 --owner=0 --group=0 data.json meta.json *.zip *.jpg
ls -lh /tmp/dbexport/smart-corridor-ri.tar.bz2
tar -tjvf /tmp/dbexport/smart-corridor-ri.tar.bz2 | head
```

## 9) Place Final Tar In Repo

```bash
cp /tmp/dbexport/smart-corridor-ri.tar.bz2 \
  '<local-path>'/edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe/smart-corridor/src/webserver/smart-corridor-ri.tar.bz2
```

## 10) Optional Cleanup

```bash
rm -rf /tmp/dbexport
```
