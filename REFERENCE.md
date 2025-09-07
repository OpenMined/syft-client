# Reference Implementation Notes

## Working Features from andrew_nonsense_4:
- Google Forms API integration (create_public_google_form_inbox)
- Form submission via HTTP POST (submit_to_form_fast) 
- Lazy form metadata caching
- Google Sheets data retrieval
- Wizard with authuser support
- Proper error handling for Forms API access

## Key Learnings:
- Forms must use "view": "published" for public access
- Form URLs change when permissions change
- Entry IDs can be extracted from form HTML
- Forms have ~37KB practical limit per submission
- Sheets cells support ~50KB

## Files to reference:
- ~/Desktop/Laboratory/syft-client-reference/gdrive_unified.py
- ~/Desktop/Laboratory/syft-client-reference/wizard.py