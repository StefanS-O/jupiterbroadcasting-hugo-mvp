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
* data structure for hosts
* Multishow capable
* Integrate Gitlab Actions for deployment
* Tags

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

## Credits

I took parts of the functionality from the Castanet Theme: https://github.com/mattstratton/castanet
Mainly the RSS feed generation and managing of hosts / guests.

Time spend so far: 9h
