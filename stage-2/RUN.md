# RUN instructions for Stage 1

## Build Container
```sh
docker build -t pocketful-stage1 .
```

## Run Container
```sh
docker run -d --rm -p 8080:8080 -e PORT=8080 pocketful-stage1
```

## Health Check
```sh
curl http://localhost:8080/health
```
