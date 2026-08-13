# Local Development

Local development is performed on Windows during the bootstrap stage.

When Hypercorn is stopped with `Ctrl+C`, Windows may print an `InterruptedError` traceback from inside Hypercorn or Python multiprocessing internals. If the server was running normally before shutdown and `/health` responded successfully, this traceback does not indicate an application failure.

Production is planned for Linux on NetAngels. Do not mask this upstream/server-level shutdown behavior in application code.

