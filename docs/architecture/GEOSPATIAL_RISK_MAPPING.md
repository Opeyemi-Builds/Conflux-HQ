# Geospatial Complaint & Outage Aggregation (Nigeria 36 States)

## Overview

ConfluxHQ maps incoming customer complaints, terminal declines, and network outages across all 36 Nigerian states and the Federal Capital Territory (FCT).

## Risk Score Formulation

The state risk metric ($R_{state}$) is computed on a 0–100 scale:

$$R_{state} = \min(100, 0.4 \cdot V_{norm} + 0.3 \cdot D_{fail} + 0.3 \cdot S_{fraud})$$

Where:
- $V_{norm}$: Normalized complaint volume over trailing 3 hours.
- $D_{fail}$: Terminal and switch decline percentage.
- $S_{fraud}$: High-severity security/fraud escalation ratio.

## Regions Monitored

- **South West**: Lagos, Ogun, Oyo, Osun, Ondo, Ekiti
- **South South**: Rivers, Delta, Edo, Akwa Ibom, Cross River, Bayelsa
- **South East**: Anambra, Enugu, Imo, Abia, Ebonyi
- **North Central**: FCT Abuja, Plateau, Benue, Kwara, Niger, Nasarawa, Kogi
- **North West**: Kano, Kaduna, Katsina, Sokoto, Kebbi, Zamfara, Jigawa
- **North East**: Borno, Adamawa, Bauchi, Gombe, Taraba, Yobe
