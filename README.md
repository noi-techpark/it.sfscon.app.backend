# opencon


### Requirements

the following software is requirement on your server to be able to run this
app

- nginx
- docker
- docker compose
- postgresql 14+

### Installation

- checkout this repository
- run docker compose build
- setup .env file (from .env.sample)
- setup global nginx (see configuration file in config/nginx.global.conf.sample
- run docker compose up -d

currently and by default, the database has been setup on host machine
visible from docker containers on host.docker.internal

this is defined at the top of .env file as

```
DB_HOST=host.docker.internal
DB_USERNAME=opencon_user	# or any other your username
DB_PASSWORD=__your_password__
DB_NAME=opencon_db		# or any other database name
DB_PORT=5432
```

create database __db_name__ with read/write/create_tables privilege for
__your_user__

as postgres admin

```
create role opencon_user with login createdb password '123';
```

as opencon_user

```
psql -U opencon_user template1
create database opencon_db
```

### bootstrap

- run docker compose up -d

from your browser open target url and login with username/password defined
in .env

ADMIN_USERNAME=__your_admin_username__
ADMIN_PASSWORD=__your_admin_password__

click to sync button to sync initial content from sfscon.it

