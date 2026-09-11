# Troubleshooting

## Scene Import Fails with `No JSON found in scenes/*.zip`

Either the Git LFS extension is not installed, or `git lfs pull` did not run,
so the scene bundle is still a small LFS pointer file instead of the real binary.

Confirm that scenes/Showcase.zip is an actual scene archive or only a Git LFS
pointer, then fix it:

```bash
$ file scenes/Showcase.zip
scenes/Showcase.zip: ASCII text          # should be "Zip archive data", not text

$ head -c 60 scenes/Showcase.zip
version https://git-lfs.github.com/spec/v1              # confirms it's an LFS pointer

$ sudo apt install git-lfs
$ git lfs install
$ git lfs pull
$ file scenes/Showcase.zip
scenes/Showcase.zip: Zip archive data, at least v2.0 to extract   # fixed
```

Then rerun:

```bash
./setup.sh
```

## `setup.sh` Succeeds But `SCENESCAPE_UI_URL` or `DASHBOARD_URL` is Unreachable from
the Browser

This is almost always host DNS or proxy configuration rather than a service problem.

Confirm that the stack is healthy and reachable locally:

```bash
docker compose ps
curl -k https://localhost/api/v1/database-ready
```

If those local checks succeed but the configured hostname in `$PUBLIC_HOSTNAME` is still
not reachable, verify the host DNS mapping and machine IP address.
Replace `my-host.example.com` with your `$PUBLIC_HOSTNAME`.
Replace `10.1.2.50` with your machine's IP.

**Check 1 — stale DNS.** `getent hosts $PUBLIC_HOSTNAME` must resolve to this machine's own IP address (compare with `hostname -I`):

```bash
$ getent hosts my-host.example.com
10.1.2.200      my-host.example.com        # wrong — not this machine's IP

$ hostname -I
10.1.2.50 172.17.0.1 ...                   # this machine is actually 10.1.2.50
```

Fix by adding a corrected entry to `/etc/hosts` (needs sudo):

```bash
echo "10.1.2.50 my-host.example.com" | sudo tee -a /etc/hosts
```

**Check 2 — request to hostname is sent to the corporate proxy instead of the Smart Building deployment.**
With `HTTP_PROXY` and `HTTPS_PROXY` set, requests to `$PUBLIC_HOSTNAME` can still be routed through
the corporate proxy and time out with HTTP 504, even after DNS is fixed, because `no_proxy` lists
only the raw IP and not the hostname or domain:

```bash
$ curl -sk -o /dev/null -w "%{http_code}\n" https://my-host.example.com/api/v1/database-ready
504                                                       # proxy can't reach the private IP

$ curl -sk --noproxy '*' -o /dev/null -w "%{http_code}\n" https://my-host.example.com/api/v1/database-ready
200                                                       # works once the proxy is bypassed — confirms the proxy is the cause
```

Add the internal domain to `no_proxy` and `NO_PROXY`, for example `.example.com`, and check
that nothing later in `~/.bashrc` or other shell startup files re-exports `no_proxy` or
`NO_PROXY` without it, because a later export `no_proxy=...` silently overwrites rather
than appends to an earlier one. Restart the browser afterward so it picks up the change.


