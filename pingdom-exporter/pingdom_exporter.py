#!/usr/bin/env python

import urllib.request
import json
import traceback
import argparse
import sys
import time
import logging
import yaml
import os
import prometheus_client
import prometheus_client.core

# parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('--config', default=sys.argv[0] + '.yml', help='config file location')
parser.add_argument('--log_level', help='logging level')
parser.add_argument('--url', help='pingdom web UI url')
parser.add_argument('--tasks', help='tasks to execute')
args = parser.parse_args()

# add prometheus decorators
REQUEST_TIME = prometheus_client.Summary('request_processing_seconds', 'Time spent processing request')

def get_config(args):
    '''Parse configuration file and merge with cmd args'''
    for key in vars(args):
        conf[key] = vars(args)[key]
    with open(conf['config']) as conf_file:
        conf_yaml = yaml.load(conf_file, Loader=yaml.FullLoader)
    for key in conf_yaml:
        if not conf.get(key):
            conf[key] = conf_yaml[key]
    token = os.environ.get('PINGDOM_EXPORTER_TOKEN')
    if token:
        conf['token'] = token

def configure_logging():
    '''Configure logging module'''
    log = logging.getLogger(__name__)
    log.setLevel(conf['log_level'])
    FORMAT = '%(asctime)s %(levelname)s %(message)s'
    logging.basicConfig(format=FORMAT)
    return log

# Decorate function with metric.
@REQUEST_TIME.time()
def get_data():
    '''Get data from target service'''
    for task_name in conf['tasks']:
        get_data_function = globals()['get_data_'+ task_name]
        get_data_function()
                
def get_data_checks():
    '''Get checks data via API'''
    # prepare request
    req = urllib.request.Request(conf['url'])
    headers = conf.get('headers')
    if headers:
        for key in headers:
            val = headers[key]
            req.add_header(key, val)
    else:
        req.add_header('Authorization', 'Bearer {0}'.format(conf['token']))
    # get data
    responce = urllib.request.urlopen(req, timeout=conf['timeout'])
    raw_data = responce.read().decode()
    json_data = json.loads(raw_data)
    parse_data_checks(json_data)

def parse_data_checks(json_data):
    '''Parse checks data received via API'''
    for check in json_data['checks']:
#       log.info('{0}\n'.format(check))
        labels = dict()
        labels['id'] = label_clean(check['id'])
        labels['name'] = label_clean(check['name'])
        labels['hostname'] = label_clean(check['hostname'])
        labels['resolution'] = label_clean(check['resolution'])
        labels['type'] = label_clean(check['type'])
        labels['ipv6'] = label_clean(check['ipv6'])
        labels['verify_certificate'] = label_clean(check['verify_certificate'])

        timestamp_metrics = {
            'created': 'Creating time. Format is UNIX timestamp',
            'lasterrortime': 'Timestamp of last error (if any). Format is UNIX timestamp',
            'lasttesttime': 'Timestamp of last test (if any). Format is UNIX timestamp'
        }

        for name in timestamp_metrics:
            metric_name = '{0}_exporter_check_{1}_timestamp_seconds'.format(conf['name'], name)
            description = timestamp_metrics[name]
            value = check[name]
            metric = {'metric_name': metric_name, 'labels': labels, 'description': description, 'value': value}
            data.append(metric)

        metric_name = '{0}_exporter_check_lastresponsetime_seconds'.format(conf['name'])
        description = 'Response time in seconds of last test.'
        value = check['lastresponsetime'] / 1000
        metric = {'metric_name': metric_name, 'labels': labels, 'description': description, 'value': value}
        data.append(metric)

        metric_name = '{0}_exporter_check_status'.format(conf['name'])
        description = 'Current status of check ({0})'.format(conf['status_map'])
        value = conf['status_map'][check['status']]
        metric = {'metric_name': metric_name, 'labels': labels, 'description': description, 'value': value}
        data.append(metric)

def label_clean(label):
    replace_map = {
        '\\': '',
        '"': '',
        '\n': '',
        '\t': '',
        '\r': '',
        '-': '_',
        ' ': '_'
    }
    for r in replace_map:
        label = str(label).replace(r, replace_map[r])
    return label

# run
conf = dict()
get_config(args)
log = configure_logging()
data = list()

pingdom_exporter_up = prometheus_client.Gauge('pingdom_exporter_up', 'pingdom exporter scrape status')
pingdom_exporter_errors_total = prometheus_client.Counter('pingdom_exporter_errors_total', 'exporter scrape errors total counter')

#class Collector(object):
class Collector():
    def collect(self):
        # add static metrics
        gauge = prometheus_client.core.GaugeMetricFamily
        counter = prometheus_client.core.CounterMetricFamily
        # get dinamic data
        try:
            get_data()
            pingdom_exporter_up.set(1)
        except:
            trace = traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
            for line in trace:
                log.error('{0}\n'.format(line[:-1]))
            pingdom_exporter_up.set(0)
            pingdom_exporter_errors_total.inc()
        # add dinamic metrics
        to_yield = set()
        for _ in range(len(data)):
            metric = data.pop()
            labels = list(metric['labels'].keys())
            labels_values = [ metric['labels'][k] for k in labels ]
            if metric['metric_name'] not in to_yield:
                setattr(self, metric['metric_name'], gauge(metric['metric_name'], metric['description'], labels=labels))
            if labels:
                getattr(self, metric['metric_name']).add_metric(labels_values, metric['value'])
                to_yield.add(metric['metric_name'])
        for metric in to_yield:
            yield getattr(self, metric)

registry = prometheus_client.core.REGISTRY
registry.register(Collector())

prometheus_client.start_http_server(conf['listen_port'])

# endless loop
while True:
    try:
        while True:
            time.sleep(conf['check_interval'])
    except KeyboardInterrupt:
        break
    except:
        trace = traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
        for line in trace:
            log.error('{0}\n'.format(line[:-1]))

