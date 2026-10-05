from whitenoise.storage import CompressedManifestStaticFilesStorage


class SchoolManagerManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Content-hashed assets in production without brittle missing-manifest failures."""

    manifest_strict = False

    def stored_name(self, name):
        """Use the unhashed path until collectstatic has produced a manifest."""
        try:
            return super().stored_name(name)
        except ValueError:
            return name

    def url_converter(self, name, hashed_files, template=None):
        """Keep unresolved vendor source-map references instead of aborting publication."""
        converter = super().url_converter(name, hashed_files, template)

        def tolerant_converter(matchobj):
            try:
                return converter(matchobj)
            except ValueError:
                return matchobj.groupdict()["matched"]

        return tolerant_converter
