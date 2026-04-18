CAMPAIGN_FLOWS = {
    "default": {
        "allowed_products": ["premium broadband", "family mobile plan", "smart home security"],
        "mandatory_disclaimer": "Prices may vary by region and taxes.",
    },
    "retention": {
        "allowed_products": ["family mobile plan", "premium broadband"],
        "mandatory_disclaimer": "Retention offers require eligibility verification.",
    },
}


RESTRICTED_PHRASES = {
    "guaranteed profit",
    "lifetime free",
    "no terms and conditions",
}
