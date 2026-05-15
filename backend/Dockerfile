FROM golang:1.22-bookworm AS builder
WORKDIR /app
COPY go.mod ./
COPY . .
RUN go build -o server main.go

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/server .
COPY frontend/dist ./frontend/dist
ENV PORT=8080
EXPOSE 8080
CMD ["./server"]
