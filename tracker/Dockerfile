FROM golang:1.23-bookworm AS base

WORKDIR /build

COPY go.mod go.sum ./

RUN go mod download

COPY . .

RUN go build -o peers-tracker

EXPOSE 8080

# Start the application
CMD ["/build/peers-tracker"]
