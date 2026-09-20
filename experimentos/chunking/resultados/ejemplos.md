# Ejemplos cualitativos

## Una tabla que A corta por la mitad

GOOGL FY2024 Item 8, caracteres 84553–85957, 17 filas.

Original:

```
Foreign Currency Translation Adjustments |  | Unrealized Gains (Losses) on Available-for-Sale Investments |  | Unrealized Gains (Losses) on Cash Flow Hedges |  | Total
Balance as of December 31, 2021 | $ | ( 2,306 ) |  |  | $ | 236 |  |  | $ | 447 |  |  | $ | ( 1,623 )
Other comprehensive income (loss) before reclassifications | ( 1,836 ) |  |  | ( 4,720 ) |  |  | 1,463 |  |  | ( 5,093 )
Amounts excluded from the assessment of hedge effectiveness recorded in AOCI | 0 |  |  | 0 |  |  | ( 188 ) |  |  | ( 188 )
Amounts reclassified from AOCI | 0 |  |  | 1,007 |  |  | ( 1,706 ) |  |  | ( 699 )
Other comprehensive income (loss) | ( 1,836 ) |  |  | ( 3,713 ) |  |  | ( 431 ) |  |  | ( 5,980 )
Balan […]
```

**A (baseline)**

`GOOGL-2024-8-0056` · 500 tok · **lo corta**

```
Accumulated Other Comprehensive Income (Loss)

Components of AOCI, net of income tax, were as follows (in millions):

Foreign Currency Translation Adjustments |  | Unrealized Gains (Losses) on Available-for-Sale Investments |  | Unrealized Gains (Losses) on Cash Flow Hedges |  | Total
Balance as of December 31, 2021 | $ | ( 2,306 ) |  |  | $ | 236 |  |  | $ | 447 |  |  | $ | ( 1,623 )
Other comprehensive income (loss) before reclassifications | ( 1,836 ) |  |  | ( 4,720 ) |  |  | 1,463 |  |  | ( 5,093 )
Amounts excluded from the assessment of hedge effectiveness recorded in AOCI | 0 |  |  | 0 |  |  | ( 188 ) |  |  | ( 188 )
Amounts reclassified from AOCI | 0 |  |  | 1,007 |  |  | ( 1,706 ) | […]
```

`GOOGL-2024-8-0057` · 405 tok · **lo corta**

```
ifications | ( 1,673 ) |  |  | ( 116 ) |  |  | 698 |  |  | ( 1,091 )
Amounts excluded from the assessment of hedge effectiveness recorded in AOCI | 0 |  |  | 0 |  |  | 77 |  |  | 77
Amounts reclassified from AOCI | 0 |  |  | 782 |  |  | ( 166 ) |  |  | 616
Other comprehensive income (loss) | ( 1,673 ) |  |  | 666 |  |  | 609 |  |  | ( 398 )
Balance as of December 31, 2024 | $ | ( 5,080 ) |  |  | $ | ( 299 ) |  |  | $ | 579 |  |  | $ | ( 4,800 )

The effects on net income of amounts reclassified from AOCI were as follows (in millions):

76.

Table of Contents | Alphabet Inc.

Year Ended December 31,
AOCI Components |  | Location | 2022 |  | 2023 |  | 2024
Unrealized gains (losses) on availabl […]
```

**C (table-aware)**

`GOOGL-2024-8-0045` · 441 tok · contiene el tramo entero

```
Components of AOCI, net of income tax, were as follows (in millions):

Foreign Currency Translation Adjustments |  | Unrealized Gains (Losses) on Available-for-Sale Investments |  | Unrealized Gains (Losses) on Cash Flow Hedges |  | Total
Balance as of December 31, 2021 | $ | ( 2,306 ) |  |  | $ | 236 |  |  | $ | 447 |  |  | $ | ( 1,623 )
Other comprehensive income (loss) before reclassifications | ( 1,836 ) |  |  | ( 4,720 ) |  |  | 1,463 |  |  | ( 5,093 )
Amounts excluded from the assessment of hedge effectiveness recorded in AOCI | 0 |  |  | 0 |  |  | ( 188 ) |  |  | ( 188 )
Amounts reclassified from AOCI | 0 |  |  | 1,007 |  |  | ( 1,706 ) |  |  | ( 699 )
Other comprehensive income (loss […]
```

## Una oración que A parte en dos

META FY2024 Item 1A, caracteres 45954–47093, 1139 caracteres.

Original:

```
Our brands may also be negatively affected by the actions of users that are deemed to be hostile or inappropriate to other users, by the actions of users acting under false or inauthentic identities, by the use of our products or services to disseminate information that is deemed to be misleading (or intended to manipulate opinions), by perceived or actual efforts by governments to obtain access to user information for security-related purposes or to censor certain content on our platform, by the use of our products or services for illicit or objectionable ends, including, for example, any such actions around geopolitical events or elections in the United States and around the world, by deci […]
```

**A (baseline)**

`META-2024-1A-0019` · 500 tok · **lo corta**

```
and innovative products, which we may not do successfully. We may introduce new products, terms of service, or policies that users do not like, which may negatively affect our brands. Additionally, the actions of our developers or advertisers may affect our brands if users do not have a positive experience using third-party applications integrated with our products or interacting with parties that advertise through our products. We will also continue to experience media, legislative, or regulatory scrutiny of our actions or decisions regarding user privacy, data use, encryption, content, product design, algorithms, advertising, competition, generative AI, younger users, and other issues, inc […]
```

`META-2024-1A-0020` · 500 tok · **lo corta**

```
by the use of our products or services to disseminate information that is deemed to be misleading (or intended to manipulate opinions), by perceived or actual efforts by governments to obtain access to user information for security-related purposes or to censor certain content on our platform, by the use of our products or services for illicit or objectionable ends, including, for example, any such actions around geopolitical events or elections in the United States and around the world, by decisions or recommendations regarding content on our platform from the independent Oversight Board, by research or media reports concerning the perceived or actual impacts of our products or services on  […]
```

**B (sentence-window)**

`META-2024-1A-0022` · 465 tok · contiene el tramo entero

```
Our brands may also be negatively affected by the actions of users that are deemed to be hostile or inappropriate to other users, by the actions of users acting under false or inauthentic identities, by the use of our products or services to disseminate information that is deemed to be misleading (or intended to manipulate opinions), by perceived or actual efforts by governments to obtain access to user information for security-related purposes or to censor certain content on our platform, by the use of our products or services for illicit or objectionable ends, including, for example, any such actions around geopolitical events or elections in the United States and around the world, by deci […]
```
