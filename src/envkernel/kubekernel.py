#!/usr/bin/env python3

import argparse
import json
import os
from os.path import join as pjoin
from pprint import pformat
# import re
# import shlex
# import shutil
import subprocess
import sys
import time
# import tempfile

import yaml

from envkernel.envkernel import envkernel, LOG, split_doubledash, printargs


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

        LOG.info(f"before split {self.argv=}")
        argv, rest = split_doubledash(self.argv, 1)
        LOG.info(f"after split {self.argv=}")
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

        args = parser.parse_args(argv)

        pod_name = f"python-test-{os.getpid()}"
        LOG.info(f"after parse {str(args)=}")
        LOG.info(f"{str(rest)=}")
        for i, arg in enumerate(rest):
            if "{connection_file}" in arg:
                rest[i] = arg.format(connection_file=args.connection_file)

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
            "kubectl", "port-forward", f"po/{pod_name}",
        ]
        # Find all the (five) necessary ports
        for var in ('shell_port', 'iopub_port', 'stdin_port', 'control_port', 'hb_port'):
            # Forward each port to itself
            port = connection_data[var]
            #expose_ports.append((connection_data[var], connection_data[var]))
            forward_cmd.append(str(port))
        # Mount the connection file inside the container
        # extra_mounts.extend(["--mount",
        #                      "type=bind,source={},destination={},ro={}".format(
        #                          connection_file, connection_file, 'false'
        #                                                                       )
        #                     ])
        #expose_mounts.append(dict(src=json_file, dst=json_file))

        # Change connection_file to bind to all IPs.
        connection_data['ip'] = '0.0.0.0'
        open(connection_file, 'w').write(json.dumps(connection_data, indent=2))
        filename = os.path.basename(connection_file)
        file_path = os.path.dirname(connection_file)

        config.load_kube_config(
            config_file="/m/home/home4/42/laines5/unix/.kube/config.d/k8s-cs",
            context="k8s-cs/jupyter-test",
        )
        script_path = os.path.dirname(os.path.realpath(__file__))
        yaml_file = f"{script_path}/pod.yaml"
        data = yaml.safe_load(open(yaml_file))
        data["metadata"]["name"] = pod_name
        data["spec"]["securityContext"]["runAsUser"] = os.getuid()
        data["spec"]["securityContext"]["runAsGroup"] = os.getgid()
        data["spec"]["securityContext"]["fsGroup"] = os.getgid()
        data["spec"]["containers"][0]["image"] = args.image
        data["spec"]["containers"][0]["command"] = rest
        data["spec"]["containers"][0]["volumeMounts"][0]["mountPath"] = file_path
        data["spec"]["volumes"][0]["configMap"]["name"] = f"connection-file-{os.getpid()}"
        data["spec"]["volumes"][0]["configMap"]["items"] = [
            {
                "key": filename,
                "path": filename,
            }
        ]


        with client.ApiClient() as k8s_client:
            api_instance = client.CoreV1Api(k8s_client)
            body = client.V1ConfigMap(
                kind="ConfigMap",
                metadata=client.V1ObjectMeta(
                    name=f"connection-file-{os.getpid()}",
                    namespace="jupyter-test",
                ),
                data={
                    filename: open(connection_file).read(),
                },
            )
            # try:
            #     api_instance.delete_namespaced_config_map(
            #         name="connection-file",
            #         namespace="jupyter-test",
            #     )
            # except client.exceptions.ApiException as e:
            #     if e.status != 404:
            #         raise
            # try:
            #     api_instance.delete_namespaced_pod(
            #         name="python-test",
            #         namespace="jupyter-test",
            #     )
            # except client.exceptions.ApiException as e:
            #     if e.status != 404:
            #         raise
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
#         cmd.extend([
#             *unknown_args,
# #           '--debug',
#             args.image,
#             *rest,
#             ])

        # Run...
        # ret = self.execvp(cmd[0], cmd)
        LOG.info(f"kubernetes: creating from dict = {pformat(data)}")
        utils.create_from_dict(
            k8s_client, data, verbose=True, namespace="jupyter-test"
        )

        def _wait_for_container(name: str, timeout: int = 60):
            with client.ApiClient() as k8s_client:
                api_instance = client.CoreV1Api(k8s_client)
                for _ in range(timeout):
                    try:
                        ret = api_instance.read_namespaced_pod_status(
                            name=name,
                            namespace="jupyter-test",
                        )
                        if ret.status.phase == 'Running':
                            return
                    except client.exceptions.ApiException as e:
                        if e.status != 404:
                            raise
                    time.sleep(1)

        _wait_for_container(pod_name)
        LOG.info("kubernetes: container is running, waiting for a little more")
        time.sleep(1)
        LOG.info(f"kubernetes: forwarding ports cmd = {printargs(forward_cmd)}")
        subprocess.Popen(forward_cmd)

        # Clean up all temparary directories
        # for tmpdir in tmpdirs:
        #     tmpdir.cleanup()
        # return(ret)
