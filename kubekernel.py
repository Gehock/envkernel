#!/usr/bin/env python3

import argparse
import copy
import glob
import json
import logging
import os
from os.path import join as pjoin
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

import yaml

from envkernel import envkernel, LOG, split_doubledash, printargs


class kubernetes(envkernel):
    def setup(self):
        super().setup()
        parser = argparse.ArgumentParser()
        parser.add_argument('image')
        args, unknown_args = parser.parse_known_args(self.argv)
        LOG.debug('setup: %s', args)

        kernel = self.get_kernel()
        kernel['argv'] = [
            os.path.realpath(sys.argv[0]),
            'kubernetes',
            'run',
            '--connection-file', '{connection_file}',
            args.image,
            *unknown_args,
            '--',
            *kernel['argv'],
        ]
        if 'display_name' not in kernel:
            kernel['display_name'] = "Kubernetes with {}".format(args.image)
        self.install_kernel(kernel, name=self.name, user=self.user,
                            replace=self.replace, prefix=self.prefix)

    def run(self):
        super().run()
        from kubernetes import client, config, utils

        argv, rest = split_doubledash(self.argv, 1)
        parser = argparse.ArgumentParser()
        parser.add_argument('image', help='Docker image name')
        #parser.add_argument('--mount', '-m', action='append', default=[],
        #                        help='mount to set up, format hostDir:containerMountPoint')
        # parser.add_argument('--copy-workdir', default=False, action='store_true')
        # parser.add_argument('--pwd', action='store_true',
        #                     help="Also mount the Jupyter working directory (containing the notebook) "
        #                          "in the image.  This is needed if you want to access data from this dir.")
        # parser.add_argument('--workdir', help='Location to mount working dir inside the container')
        parser.add_argument('--connection-file', help="Do not use, internal use.")

        args, unknown_args = parser.parse_known_args(argv)

        # extra_mounts = [ ]

        # # working dir
        # if args.pwd or args.workdir:
        #     workdir = os.getcwd()
        #     if args.workdir:
        #         workdir = args.workdir
        #     # src = host data, dst=container mountpoint
        #     extra_mounts.extend(["--mount", "type=bind,source={},destination={},ro={}{}".format(os.getcwd(), workdir, 'false', ',copy' if args.copy_workdir else '')])

        cmd = [
            "docker", "run", "--rm", "-i",
            "--user", "%d:%d"%(os.getuid(), os.getgid()),
            ]

        # Parse connection file
        connection_file = args.connection_file
        connection_data = json.load(open(connection_file))
        forward_cmd = [
            "kubectl", "port-forward", "po/python-test",
        ]
        # Find all the (five) necessary ports
        for var in ('shell_port', 'iopub_port', 'stdin_port', 'control_port', 'hb_port'):
            # Forward each port to itself
            port = connection_data[var]
            #expose_ports.append((connection_data[var], connection_data[var]))
            forward_cmd.append(port)
        # Mount the connection file inside the container
        # extra_mounts.extend(["--mount",
        #                      "type=bind,source={},destination={},ro={}".format(
        #                          connection_file, connection_file, 'false'
        #                                                                       )
        #                     ])
        #expose_mounts.append(dict(src=json_file, dst=json_file))

        # Change connection_file to bind to all IPs.
        connection_data['ip'] = '0.0.0.0'
        open(connection_file, 'w').write(json.dumps(connection_data))
        filename = os.path.basename(connection_file)

        config.load_kube_config(
            config_file="/m/home/home4/42/laines5/unix/.kube/config.d/k8s-cs",
            context="k8s-cs/jupyter-test",
        )
        yaml_file = "pod.yaml"
        data = yaml.safe_load(open(yaml_file))
        data["spec"]["securityContext"]["runAsUser"] = os.getuid()
        data["spec"]["securityContext"]["runAsGroup"] = os.getgid()
        data["spec"]["securityContext"]["fsGroup"] = os.getgid()



        with client.ApiClient() as k8s_client:
            body = client.V1ConfigMap(
                api_version="v1",
                kind="ConfigMap",
                metadata=client.V1ObjectMeta(
                    name="connection-file",
                    namespace="jupyter-test",
                ),
                data={
                    filename: connection_data,
                },
            )
            api_instance = client.CoreV1Api(k8s_client)
            api_instance.create_namespaced_config_map(
                namespace="jupyter-test",
                body=body,
            )

        # Add options to expose the ports
#       for port_host, port_container in expose_ports:
#           cmd.extend(['--expose={}'.format(port_container), "-p", "{}:{}".format(port_host, port_container)])

        ## Add options for exposing mounts
        #tmpdirs = [ ]  # keep reference to clean up later
        #for mount in expose_mounts:
        #    src = mount['src']  # host data
        #    dst = mount['dst']  # container mountpoint
        #    if mount.get('copy'):
        #        tmpdir = tempfile.TemporaryDirectory(prefix='jupyter-secure-')
        #        tmpdirs.append(tmpdir)
        #        src = tmpdir.name + '/copy'
        #        shutil.copytree(mount['src'], src)
        #    cmd.extend(["--mount", "type=bind,source={},destination={},ro={}".format(src, dst, 'true' if mount.get('ro') else 'false')])  # ro=true
        #cmd.extend(("--workdir", workdir))

        # Process all of our mounts, to do two things:
        #  Substitute {workdir} with
        # unknown_args.extend(extra_mounts)
        # tmpdirs = []
        # for i, arg in enumerate(unknown_args):
        #     if '{workdir}' in arg and args.copy_workdir:
        #         arg = arg + ',copy'
        #     arg.format(workdir=os.getcwd)
        #     if ',copy' in arg:
        #         src_original = re.search('src=([^,]+)', arg).group(1)
        #         # Copy the source directory
        #         tmpdir = tempfile.TemporaryDirectory(prefix='jupyter-secure-')
        #         tmpdirs.append(tmpdir)
        #         src = tmpdir.name + '/copy'
        #         shutil.copytree(src_original, src)
        #         #
        #         newarg = re.sub('src=([^,]+)', 'src='+src, arg) # add in new src
        #         newarg = re.sub(',copy', '', newarg)            # remove ,copy
        #         unknown_args[i] = newarg

        # Image name
#       cmd.append(args.image)

        # Remainder of all other arguments from the kernel specification
        cmd.extend([
            *unknown_args,
#           '--debug',
            args.image,
            *rest,
            ])

        # Run...
        LOG.info('kubernetes: running cmd = %s', printargs(cmd))
        subprocess.Popen(forward_cmd)
        ret = self.execvp(cmd[0], cmd)

        # Clean up all temparary directories
        # for tmpdir in tmpdirs:
        #     tmpdir.cleanup()
        return(ret)
