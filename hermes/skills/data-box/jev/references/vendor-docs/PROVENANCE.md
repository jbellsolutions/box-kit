# jev vendor docs

The kit ships the list of sources ([SOURCES.json](SOURCES.json)) but not the vendor's pages: they
are the vendor's to publish. Fetch your own dated, hashed copy from the kit's root:

```bash
cd server/data-box && python3 -m data_box.vendor_docs fetch ../../plugins/data-box/skills/jev
```

That writes pages/, manifest.json and a new PROVENANCE.md here, through the same public-only fetch
data-box uses for scraping. Only free, public pages are fetched.
