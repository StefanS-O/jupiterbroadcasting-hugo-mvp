# Jupiter Broadcasting MVP

Build with Hugo and deployed with Github Actions

Demo: https://jb.codefighters.net

https://github.com/JupiterBroadcasting/jupiterbroadcasting.com/discussions/8#discussioncomment-2731384

## Features

* Static Site using Hugo
* Complete publishing workflow using Github and Github Actions
* Template using SCSS (without node dependencies using Hugo extended)
* only Vanilla JS is used (single files with concat workflow)
* Highly configurable with config.toml and config folder
* Hosts (via data folder and frontmatter)
* Video player
* HTML5 audio player
* Multishow capable
* Tags (via frontmatter)
* Guests (via data folder and frontmatter)
* Sponsors (via data folder and frontmatter)

## ToDo

* RSS feed generation
* Search Function (probably Lunr)
* Contact Form (?)
* adding more content
* write better docs

## Setup

### Using Hugo binary

Install Hugo: https://gohugo.io/getting-started/installing/

Start the development Server (rebuild on every filesystem change)

`hugo server -D`

### Using Docker

tbd

### run for different Site

`hugo server -D --config config.coderradio.toml`

to clean the module config

`hugo mod clean --all`


build

`hugo -D --config config.coderradio.toml`

Hugo issue currently regarding overlapping mounts

https://github.com/gohugoio/hugo/issues/7123

so for now only subdirectories work

## Deployment

Deployment is done with Github Actions, see workflow file in `.github/workflows/main.yml`
At the moment it is only triggered when something in the `main` branch is changing, but it can also be set up to run at certain times.
This would also enable scheduled publishing, since Hugo per default only build pages which have set `date` in frontmatter to <= `now`

## Credits

I took parts of the functionality from the Castanet Theme: https://github.com/mattstratton/castanet
Mainly the RSS feed generation and managing of hosts / guests.

Time spend so far: 13h
