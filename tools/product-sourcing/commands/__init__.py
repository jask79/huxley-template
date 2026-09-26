"""
Product Sourcing CLI command modules.

Each subcommand lives in its own file and exposes a `run(args, db_conn, clients)` function.
Command modules are imported lazily by cli.py to keep startup fast.
"""
