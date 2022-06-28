dev:
	hugo server -D

build:
	hugo -D

run:
	docker-compose up -d --build jbsite

# Clean the scraped data
scrape-clean:
	rm -r scraped-data && mkdir scraped-data

# Execute scrapig all the data from fireside into scraped-data dir
scrape: scrape-clean
	docker-compose up -d --build fireside-scraper && \
	docker-compose logs --no-log-prefix -f fireside-scraper

# Copy contents of the scraped-data into the project
scrape-copy:
	./scrape-copy.sh && ./generate-guests-symlinks.sh

scrape-full: scrape scrape-copy
