import sys

from envkernel import envkernel, lmod, conda, virtualenv, docker, singularity

def main(argv=sys.argv):
    modules: dict[str, envkernel] = {
        "lmod": lmod,
        "conda": conda,
        "virtualenv": virtualenv,
        "docker": docker,
        "singularity": singularity,
    }

    if len(argv) <= 1 or argv[1] in {'-h', '--help'}:
        print("envkernel must be called with the name of a module as the first argument.")
        print("Currently help does not show mode-options for each module, please see the")
        print("README.")
        print("")
        print("available modules:", *sorted(modules))
        print("")
        print("General usage: envkernel [envkernel-options] [mode-options]")
        print("")
        print("envkernel-options:")
        print("")
        envkernel(["--help"]).setup()
        exit(0)

    mod = argv[1]
    if mod not in modules:
        print(f"Unknown mode: {mod}")
        print("Valid modes:", *sorted(modules))
        exit(1)

    cls = modules[mod]
    if len(argv) > 2 and argv[2] == 'run':
        return cls(argv[3:]).run()
    else:
        print(f"{cls=} {argv=}")
        cls(argv[2:]).setup()
        return 0

if __name__ == '__main__':
    exit(main())
