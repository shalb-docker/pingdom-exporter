# pingdom-exporter

pingdom exporter for prometheus monitoring

## build

~~~~
docker login
docker-compose -f docker-compose-build.yml build
docker-compose -f docker-compose-build.yml push
~~~~

## configuration

Add your headers to 'headers' section of config file pingdom-exporter/pingdom_exporter.py.yml

## run

Use docker-compose.yml to run container with mounted config pingdom-exporter/pingdom_exporter.py.yml
~~~~
docker-compose up
~~~~

