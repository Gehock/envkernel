import argparse
import json
import os
import sys

from envkernel.envkernel import envkernel, LOG, split_doubledash


class dummy(envkernel):
    def setup(self):
        super().setup()
        parser = argparse.ArgumentParser()
        parser.add_argument("--ip", help="IP to listen to", required=True)
        args, unknown_args = parser.parse_known_args(self.argv)
        LOG.debug("setup: %s", args)

        kernel = self.get_kernel()
        kernel["argv"] = [
            os.path.realpath(sys.argv[0]),
            "dummy",
            "run",
            "--connection-file",
            "{connection_file}",
            "--ip",
            args.ip,
            *unknown_args,
            "--",
            *kernel["argv"],
        ]
        if "display_name" not in kernel:
            kernel["display_name"] = f"Dummy kernel at {args.ip}"
        self.install_kernel(
            kernel,
            name=self.name,
            user=self.user,
            replace=self.replace,
            prefix=self.prefix,
        )

    def run(self):
        super().run()

        LOG.info(f"before split {self.argv=}")
        argv, rest = split_doubledash(self.argv, 1)
        LOG.info(f"after split {self.argv=}")
        parser = argparse.ArgumentParser()
        parser.add_argument("--ip", help="Internal use", required=True)
        parser.add_argument("--connection-file", help="Internal use")

        args = parser.parse_args(argv)

        LOG.info(f"after parse {str(args)=}")
        LOG.info(f"{str(rest)=}")
        for i, arg in enumerate(rest):
            if "{connection_file}" in arg:
                rest[i] = arg.format(connection_file=args.connection_file)
                break

        # Parse connection file
        connection_file = args.connection_file
        connection_data = json.load(open(connection_file))

        # Change the local connection_file to connect to the service.
        connection_data["ip"] = args.ip
        connection_json_local = json.dumps(connection_data, indent=2)
        open(connection_file, "w").write(connection_json_local)

        # Find all the (five) necessary ports
        for var in (
            "shell_port",
            "iopub_port",
            "stdin_port",
            "control_port",
            "hb_port",
        ):
            # Forward each port to itself
            port = connection_data[var]
            var = var.replace("_port", "")
            LOG.debug(f"forwarding {var} to {port}")

        LOG.info("dummy: kernel started")
