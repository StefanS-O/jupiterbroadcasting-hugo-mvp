dev:
	hugo server -D

build:
	hugo -D

run:
	docker-compose up -d --build