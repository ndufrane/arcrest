from __future__ import print_function

import argparse
import os
import sys
import time
import urlparse

import arcrest.admin

__all__ = ['createservice', 'manageservice', 'managesite']

shared_args = argparse.ArgumentParser(add_help=False)
shared_args.add_argument('-u', '--username', 
                         required=True,
                         help='Description: Username for Server')
shared_args.add_argument('-p', '--password', 
                         required=True,
                         help='Description: Password for Server')
shared_args.add_argument('-s', '--site', 
                         required=True,
                         help='Description: URL for admin Server')

createserviceargs = argparse.ArgumentParser(description='Creates a service',
                                            parents=[shared_args])
createserviceargs.add_argument('-c', '--cluster',
                               nargs='?',
                               default=None,
                               help='Name of cluster to act on')
createserviceargs.add_argument('sdfile',
                                nargs='+',
                                metavar="FILE",
                                help='Filename of local Service Definition file')
createserviceargs._optionals.title = "arguments"

manageserviceargs = argparse.ArgumentParser(description=
                                                'Manages/modifies a service',
                                            parents=[shared_args])
manageserviceargs.add_argument('-n', '--name',
                               default=None,
                               help='Description: Service name (optional)')
manageserviceargs.add_argument('-o', '--operation',
                               default=None,
                               required=True,
                               help="Description: Operation to perform on "
                                    "specified service. If -l or --list is "
                                    "specified, used as a status filter "
                                    "instead.",
                               choices=['status', 'start', 'stop', 'delete'])
manageserviceargs.add_argument('-l', '--list',
                               default=False,
                               action='store_true',
                               help="Description: List services on server "
                                    "(optional)")
manageserviceargs._optionals.title = "arguments"

managesiteargs = argparse.ArgumentParser(description=
                                                'Manages/modifies a site',
                                            parents=[shared_args])
managesiteargs.add_argument('-A', '--add-machines',
                               nargs='+',
                               help='Machines to add to cluster')
managesiteargs.add_argument('-R', '--remove-machines',
                               nargs='+',
                               help='Machines to remove from cluster')
managesiteargs.add_argument('-l', '--list',
                               default=False,
                               action='store_true',
                               help='List machines on a site')
managesiteargs.add_argument('-lc', '--list-clusters',
                               default=False,
                               action='store_true',
                               help='List clusters on a site')
managesiteargs.add_argument('-o', '--operation',
                               nargs='?',
                               help='Description: Operation to perform on cluster',
                               choices=['chkstatus', 'start', 'stop'])
managesiteargs.add_argument('-c', '--cluster',
                               nargs='?',
                               default=None,
                               help='Name of cluster to act on')
managesiteargs.add_argument('-D', '--delete-cluster',
                               default=False,
                               action='store_true',
                               help='Delete cluster specified with -c')
managesiteargs.add_argument('-cr', '--create-cluster',
                               default=False,
                               action='store_true',
                               help=('Create cluster specified with -c '
                                     'if it does not exist'))
managesiteargs._optionals.title = "arguments"


class ActionNarrator(object):
    def __init__(self):
        self.action_stack = []
    def __call__(self, action):
        self.action = action
        return self
    def __enter__(self):
        self.action_stack.append(self.action)
    def __exit__(self, t, ex, tb):
        action = self.action_stack.pop()
        if (t, ex, tb) != (None, None, None):
            if t is not SystemExit:
                print("Error {0}: {1}".format(action, str(ex)))
            sys.exit(1)

def get_rest_urls(admin_url):
    admin_url = urlparse.urljoin(admin_url, '/arcgis/admin/')
    rest_url = urlparse.urljoin(admin_url, '/arcgis/rest/')
    return (admin_url, rest_url)

def provide_narration(fn):
    def fn_():
        return fn(ActionNarrator())
    return fn_

@provide_narration
def createservice(action):
    args = createserviceargs.parse_args()
    files = args.sdfile
    admin_url, rest_url = get_rest_urls(args.site)
    with action("connecting to admin site {0}".format(admin_url)):
        site = arcrest.admin.Admin(admin_url)
    with action("connecting to REST services {0}".format(rest_url)):
        rest_site = arcrest.Catalog(rest_url)
    with action("looking up Publish Tool"):
        publish_tool = (rest_site['System']
                                 ['PublishingTools']
                                 ['Publish Service Definition'])
    with action("looking up cluster"):
        cluster = site.clusters[args.cluster] if args.cluster else None
    with action("verifying service definition file exists"):
        all_files = [os.path.abspath(filename) for filename in files]
        assert all_files, "No file specified"
        for filename in all_files:
            assert os.path.exists(filename) and os.path.isfile(filename), \
                    "{0} is not a file".format(filename)
    ids = []
    for filename in all_files:
        with action("uploading {0}".format(filename)):
            id = site.data.items.upload(filename)['packageID']
            with action("publishing {0}".format(os.path.basename(filename))):
                result_object = publish_tool(id, site.url)
                while result_object.running:
                    time.sleep(0.125)

@provide_narration
def manageservice(action):
    args = manageserviceargs.parse_args()
    admin_url, rest_url = get_rest_urls(args.site)
    if args.list:
        with action("checking arguments"):
            assert not args.name, "name cannot be set if listing services"
        with action("connecting to admin site {0}".format(admin_url)):
            site = arcrest.admin.Admin(admin_url)
        with action("listing services"):
            services = site.services
            folders = services.folders
        with action("printing services"):
            for service in services.services:
                print(service.name)
            for folder in folders:
                for service in folder.services:
                    print(folder.folderName+"/"+service.name, service.status)
    else:
        with action("checking arguments"):
            assert args.name, "Service name not specified"
        with action("connecting to admin site {0}".format(admin_url)):
            site = arcrest.admin.Admin(admin_url)
        with action("listing services"):
            services = site.services
        with action("searching for service %s" % args.name):
            service = services[args.name]
        operation = args.operation.lower()
        if operation == 'status':
            for key, item in sorted(service.status.iteritems()):
                print("{0}: {1}".format(key, item))
        elif operation == 'start':
            with action("starting service"):
                return service.start()
        elif operation == 'stop':
            with action("stopping service"):
                return service.stop()
        elif operation == 'delete':
            with action("deleting service"):
                return service.delete()

@provide_narration
def managesite(action):
    args = managesiteargs.parse_args()
    admin_url, rest_url = get_rest_urls(args.site)
    with action("connecting to admin site {0}".format(admin_url)):
        site = arcrest.admin.Admin(admin_url)
    with action("determining actions to perform"):
        assert any([
                     args.add_machines, 
                     args.remove_machines,
                     args.delete_cluster,
                     args.create_cluster,
                     args.list,
                     args.list_clusters
                ]), "No action specified (use --help for options)"
    with action("looking up cluster"):
        try:
            cluster = site.clusters[args.cluster] if args.cluster else None
        except KeyError:
            if args.create_cluster:
                cluster = site.clusters.create(args.cluster)
            else:
                raise
    with action("deleting cluster"):
        if args.delete_cluster:
            assert cluster, "Asked to delete a cluster when none was specified"
            cluster.delete()
    with action("adding machines to cluster"):
        if args.add_machines:
            assert cluster, "No cluster specified"
            for machine in args.add_machines:
                with action("adding {0} to cluster".format(machine)):
                    cluster.machines.add(machine)
    with action("removing machines from cluster"):
        if args.remove_machines:
            assert cluster, "No cluster specified"
            for machine in args.remove_machines:
                with action("deleting {0} from cluster".format(machine)):
                    cluster.machines.remove(machine)
    with action("listing machines"):
        if args.list:
            name, itemobject = ('cluster', cluster) \
                    if cluster else ('site', site)
            print("===Machines on this {0}===".format(name))
            for machine in itemobject.machines.keys():
                print("-", machine)
            print()
    with action("listing clusters"):
        if args.list_clusters:
            print("===Clusters on this site===")
            for cluster in site.clusters.clusterNames:
                print("-", cluster)
            print()
