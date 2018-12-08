#!/usr/bin/env python3
import math, os, subprocess, sys, json, io, argparse

class Color:
    sequences = {
        "red"   : "\033[91;1m",
        "green" : "\033[92;1m",
        "yellow": "\033[93;1m",
        "blue"  : "\033[94;1m",
        "purple": "\033[95;1m",
        "cyan"  : "\033[96;1m",
        "end"   : "\033[0m"
    }

    def colorize(c, s):
        return Color.sequences[c]+s+Color.sequences["end"]

    def red(s)   : return Color.colorize("red", s)
    def green(s) : return Color.colorize("green", s)
    def yellow(s): return Color.colorize("yellow", s)
    def blue(s)  : return Color.colorize("blue", s)
    def purple(s): return Color.colorize("purple", s)
    def cyan(s)  : return Color.colorize("cyan", s)

def err(s):
    print("{} {}".format(Color.red("Error:"), s))
    sys.exit(1)

def trim_trailing_slash(s):
    if s.endswith("/"):
        return s[:-1]
    return s

def confirm(s, skipped=False):
    if skipped:
        return

    ans = input(s + " [y/N] ")
    if ans != "y":
        print("Operation aborted.")
        sys.exit(3)

class Source:
    identifiers = {}
    padding = 0
    def readable(self):
        return os.access(self.path, os.R_OK)
    def unique_idn(self):
        return self.unique
    def err(self):
        errs = []
        if not self.readable():
            errs.append("not readable")
        if not self.unique_idn():
            errs.append("{} conflicts with {}".format(self.idn, Source.identifiers[self.idn]))
        return ",".join(errs)
    def size(self):
        if not hasattr(self, '__size'):
            args = ["du", "-sh", self.path]
            for excl in self.excludes:
                args += ["--exclude", self.path + "/" + excl]
            tmp = subprocess.check_output(args).decode("utf-8")
            self.__size = tmp.split()[0]
        return self.__size
    def update_padding(self):
        padding = int(len(self.path) * 1.5)
        if padding > Source.padding:
            Source.padding = padding
    def show(self, size=True):
        output = io.StringIO()
        output.write(Color.yellow("{src:<{pad}}".format(src=self.path, pad=Source.padding)))

        err = self.err()
        if err:
            output.write(Color.red(err))
        else:
            output.write(Color.green("ok"))
            if size:
                output.write("{size:>{pad}}".format(size=self.size(), pad=Source.padding))
        output.write("\n")
        if len(self.excludes) > 0:
            output.write("\texcluding\n")
            for excl in self.excludes:
                output.write("\t\t{0}\n".format(excl))
        print(output.getvalue(), end="")

    def exclude(self, s):
        self.excludes.append(s)
    def __init__(self, s):
        self.excludes = []
        self.path = trim_trailing_slash(s)
        self.idn = os.path.basename(self.path)
        self.update_padding()

        self.unique = False
        if self.idn not in Source.identifiers:
            Source.identifiers[self.idn] = s
            self.unique = True

class Target:
    def writable(self):
        return os.access(self.path, os.W_OK)
    def exists(self):
        return os.path.exists(self.path)
    def sanity(self):
        return self.exists() and self.writable()
    def create(self):
        assert not self.exists()
        confirm("Target {} does not exist - create?".format(Color.cyan(self.path)))
        try:
            os.makedirs(self.path)
        except:
            err("could not create {}".format(Color.cyan(self.path)))
    def showSource(self, source):
        location = os.path.join(self.path, source.idn)
        output = io.StringIO()
        output.write(Color.blue("{loc:<{pad}}".format(loc=location, pad=Source.padding)))
 		# Location exists?
        if not os.path.exists(location):
            output.write(Color.green("to be created"))
        else:
            output.write(Color.purple("exists"))
            size = subprocess.check_output(["du", "-sh", location]).decode("utf-8")
            size = size.split()[0]
            output.write("{size:>{pad}}".format(size=size, pad=Source.padding-4))
        print(output.getvalue())
    def rsync(self, source):
        location = os.path.join(self.path, source.idn)
        print("{}: Syncing {} => {}".format(Color.purple("backup.py"), Color.yellow(source.path), Color.blue(location) ))
        args = ["rsync", "-i", "--info=progress2", "-a", "--links", "--delete", "--delete-excluded"]
        for excl in source.excludes:
            args += ["--exclude", source.idn + "/" + excl]
        args += [source.path, self.path]
        subprocess.call(args)

    def __init__(self, s):
        self.path = s.strip()

def makelist(l):
    if type(l) == str:
        return [l]
    return l

def getpath(item):
    if type(item) == dict:
        return item["path"]
    return item

def getexclude(item):
    if type(item) != dict:
        return []
    return makelist(item["exclude"])

# Returns tuple of sources, target
def readconfig(configfile):
    with open(configfile) as f:
        config = json.load(f)

    # basic sanity
    assert len(config.keys()) == 2 and \
           type(config["sources"]) == list and \
           type(config["target"]) == str

    sources = []
    for item in config["sources"]:
        source = Source(getpath(item))
        for excl in getexclude(item):
            source.exclude(excl)
        sources.append(source)

    target = Target(config["target"])
    return (sources, target)

def getargs():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
      description="A small script to automate running rsync for backup purposes.\n")

    parser.add_argument('--config', type=str, required=True, help="Location of configuration file")
    parser.add_argument('--autoconfirm', dest='autoconfirm', action='store_true', help='Unattended mode - confirm automatically')
    parser.set_defaults(autoconfirm=False)

    args = parser.parse_args()

    args.config = os.path.expanduser(args.config)
    args.config = os.path.realpath(args.config)
    args.config = os.path.normpath(args.config)
    return args

def main():
    args = getargs()
    (sources, target) = readconfig(args.config)

    for source in sources:
        source.show()

    for source in sources:
        if source.err():
            err("one or more sources failed sanity check")

    if not target.exists():
        target.create()

    if not target.writable():
        err("target not writable")

    assert target.sanity()

    print("\nLocations to be synced:")
    for source in sources:
        target.showSource(source)

    # Final confirmation
    confirm("Proceed?")
    for source in sources:
        target.rsync(source)
    print(Color.purple("All done!"))
if __name__ == "__main__":
    main()
