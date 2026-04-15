FROM node:20-alpine AS ui-builder

WORKDIR /ui
COPY ui/package*.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

FROM golang:1.25 AS builder

ARG TARGETARCH

WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download

COPY . .
COPY --from=ui-builder /ui/dist ./ui/dist

RUN CGO_ENABLED=0 GOOS=linux GOARCH=${TARGETARCH} go build -o /out/pocketbase ./examples/base

FROM alpine:3.21

RUN apk --no-cache add ca-certificates tzdata

WORKDIR /pb

COPY --from=builder /out/pocketbase /pb/pocketbase
COPY pb_public /pb/pb_public

EXPOSE 8090

VOLUME ["/pb/pb_data", "/pb/pb_hooks", "/pb/pb_migrations"]

ENTRYPOINT ["/pb/pocketbase"]
CMD ["serve", "--http=0.0.0.0:8090"]
