# India News: transparent 72-hour weekend coverage (preview-only)

SignalDesk previously selected India News with the same 36-hour deadline as the Global/topical editorial bot. On weekends this often excluded legitimate Friday stories, leaving a nearly empty India section even when the existing approved RSS sources had reported them.

The **static preview** now uses a **rolling 72-hour** lookback for India only, with **no more than eight articles per publisher** and **50 total**. The publisher name and article publication time remain attached, articles still must be genuinely India-related, and content older than 72 hours is rejected. The website's India description and both gallery/layered explorer views visibly label the wider coverage window.

Global keeps its 36-hour selection and existing source caps. X posting and original editorial draft quotas remain disabled and unchanged. No additional feeds are polled, no Cron is created, no paid services or images are requested, and the production Worker is untouched.

**Limits:** this can increase India counts by including genuine recent stories already present in existing RSS; it cannot guarantee 50. Even with eight per publisher, there may be fewer than 50 available and permitted stories. The public live Worker is still separately deployed and would require its own rollout review to align on collection windows. This change alone does not activate the requested newspapers whose reuse permissions remain unresolved.

Tests assert an India story 71 hours old remains eligible, one 73 hours old is excluded, no Global spillover, and one publisher never exceeds eight results.
