# Automated Scaling using K8s

- Deploy the API

```bash
kubectl apply -f k8s-ghanapostgps.yaml
kubectl -n ghanapostgps rollout status deploy/ghanapostgps-api
```

- Port-forward for local access

```bash
kubectl -n ghanapostgps port-forward deploy/ghanapostgps-api 9091:9091
```

- Collect data & train

```bash
python train_autoscaler.py --base-url http://127.0.0.1:9091 --duration-secs 300 --qps 5 \
  --target-p95-ms 400 --target-rps-per-pod 8 --outfile replica_model.pkl
```

- Run autoscaler

```bash
python run_autoscaler.py --service-url http://127.0.0.1:9091 \
  --kube-namespace ghanapostgps --deployment ghanapostgps-api \
  --min-replicas 1 --max-replicas 10 --interval-secs 15 --cooldown-secs 60
```

- Generate big traffic

```bash
python load_generator.py --base-url http://127.0.0.1:9091 --concurrency 300 --duration-secs 300
```
