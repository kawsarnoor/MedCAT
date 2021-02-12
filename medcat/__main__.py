if __name__ == "__main__":
    from medcat.cli import package, download, listmodels
    import plac
    import sys

    commands = {
        "download" : download,
        "package" : package,
        "listmodels" : listmodels
    }

    if len(sys.argv) == 1:
        print("Available commands : ", ", ".join(commands))
        sys.exit()

    command = sys.argv.pop(1)
    if command in commands:
            plac.call(commands[command], sys.argv[1:])
    else:
        available = "Available: {}".format(", ".join(commands))
        print("Unknown command: {}".format(command), available)
        sys.exit()