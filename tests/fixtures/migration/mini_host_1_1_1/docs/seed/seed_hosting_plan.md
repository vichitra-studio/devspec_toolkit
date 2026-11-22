# Hosting plan

One small virtual server hosts the lending service and its PostgreSQL database in the dev, ci, staging and prod environments, region eu-west-1. Secrets DATABASE_URL and TEXTLINE_API_KEY are injected by the delivery pipeline; the pipeline runs the lint, unit-tests and schema-validate gates. Texts go through the Textline SMS API.
