#!/usr/bin/python3

import urllib.request
import json
import prometheus_client
import time
import yaml
import os
import sys
import traceback

# https://github.com/prometheus/client_python

# read config
conf_file_name = sys.argv[0] + '.yml'
with open(conf_file_name) as conf_file:
    conf = yaml.load(conf_file.read())

# Create metrics
REQUEST_TIME = prometheus_client.Summary('request_processing_seconds', 'Time spent processing request')
collector_errors = prometheus_client.Gauge('collector_errors', 'Total number of errors')
pingdom_check_status = prometheus_client.Gauge('pingdom_check_status', 'Check status', ['name', 'hostname'])

# Decorate function with metric.
@REQUEST_TIME.time()
def get_checks_stats():
    """Get pingdom checks via API."""
    # prepare request
    req = urllib.request.Request(conf['url'])
    for key in conf['headers']:
        val = conf['headers'][key]
        req.add_header(key, val)
    # get data
    result = urllib.request.urlopen(req, timeout=conf['timeout'])
    result = result.read().decode()
    result = json.loads(result)
    # add results to metrics
    if result['checks']:
        for check in result['checks']:
            status = conf['status_map'][check['status']]
            pingdom_check_status.labels(name=check['name'], hostname=check['hostname']).set(status)
    else:
        collector_errors.inc()

if __name__ == '__main__':
    prometheus_client.start_http_server(conf['listen_port'])
    try:
        while True:
            get_checks_stats()
            time.sleep(conf['check_interval'])
    except:
        trace = traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
        for line in trace:
            print(line[:-1])
        collector_errors.inc()
        time.sleep(conf['check_interval'])

