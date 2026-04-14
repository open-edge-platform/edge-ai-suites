Configure the submodules path
```ini
[DEFAULT]
root_path = C:\Users\user\jianfeng\EDU-AI\edge-ai-suites\education-ai-suite\content-search
[submodules]
content_search_minio     = %(root_path)s/content_search_minio
file_ingest_and_retrieve = %(root_path)s/file_ingest_and_retrieve
```
Create and remove softlinks
```powershell
# create softlink
python .\set_submodule.py -create -f .\conf.ini
# remove softlink
python .\set_submodule.py -remove -f .\conf.ini
```