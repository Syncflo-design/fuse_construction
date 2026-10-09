"""Sage Intacct for construction — phase 2, switched off.

Nothing in this package runs unless "Post Construction Documents to Intacct" is ticked in
FC Settings AND the Intacct connection (fuse_core) is enabled. With either off, no call is
made, no request is logged, and every construction document stays in Fuse.

The transport is fuse_core.gateway: one connection, one request log, deterministic control
IDs so a retry can never post twice. Nothing here opens its own connection.
"""
