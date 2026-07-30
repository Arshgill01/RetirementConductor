# LookML ingestion fixture

This public, non-live project exists only to validate the scoped DataHub
LookML recipe and field/connection mapping. Its model deliberately uses the
fixed disposable connection name `retirement_fixture`, because DataHub 1.6.0
does not expand environment references in mapping keys. It never connects to
or queries a warehouse.
