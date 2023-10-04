# ocsarchive-iiif

[IIIF (triple-eye-eff) Image API](https://iiif.io/api/image/3.0/) for the
[ocsarchive](https://github.com/observatorycontrolsystem/science-archive)

## Development

Install https://devenv.sh/getting-started/ and then:

```shell
devenv shell
```

Start up a development K8s cluster:

```shell
kind create cluster --config ./kind-cluster.yaml
```

And then use `skaffold` to develop.

First start up dependencies (databases, Temporal, proxies, etc):

```shell
skaffold run -p local-depends
```

And then start the development loop. It's setup such that any source-code changes
hot-reload.:

```shell
skaffold dev -p local
```

This should start port-forwarding the local ingress such that you can access the
API at <http://api.local.lco.earth:8000/> or the Temporal dashboard
at <https://temporal.local.lco.earth:8443/>.

If you run into issues with hot-reloading, just CTRL-C and re-run the command.

Workflows (and their state) are persisted by the Temporal Server.
If you *really* would like to start with a clean slate, delete those components
and re-deploy:

```shell
skaffold delete -p local-depends
kubectl delete ns temporal-ds-pg13
skaffold run -p local-depends
```
