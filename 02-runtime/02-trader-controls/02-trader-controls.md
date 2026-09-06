### Day Trader Controls

Chapter Two. 2026/06/19.

This is the control layer for the trader-swing bot: what it is allowed to do, when, and why. It moves from the widest frame down to the coding mechanics. Part 1 fixes the purpose and the strategy. Part 2 sets the governance that holds the model. Part 3 is the arithmetic of fees, volatility, and sizing. Part 4 is the coin universe and the screen that builds it. Part 5 is the build sequence and what is still open. The Chapter One manifesto is preserved verbatim in `trader-swing-manifesto-a.md`; this document is the build-out beneath it.

Reading order: Purpose and Strategic Frame; Governance Architecture; The Numbers; Coin Universe and the Screen; Build Sequence and Open Questions.

---

### 1. Purpose and Strategic Frame

#### What this system is, and is not

At roughly five hundred to a thousand dollars combined across two accounts, this is not a money-making operation and must not be run as one. Fees, day-trade rules, and spreads do not scale down kindly. Two percent on five hundred dollars is ten dollars; a single outgoing wire is twenty-five. So the goal is named plainly: a learning and proving rig. Build the architecture, validate that it has any edge at all out-of-sample, and prove the operational pipeline end to end, with real but trivial money so mistakes cost ten dollars and not ten thousand. That is the right way to start. It is not income yet, and saying so protects against the temptation to over-trade a tiny account chasing returns the fee structure will eat.

The standing result reinforces the caution. The existing engine has no demonstrated edge out-of-sample. Until walk-forward proves otherwise, every control here exists to keep an unproven model cheap and honest, not to chase performance.

#### Strategy character: selective swing

This is a selective, high-conviction swing strategy, not a scalper. Patience is the edge that survives fees. A trade held for a clean three or five percent move does not care about a 0.2 percent round trip; a trade chasing half a percent is eaten by it. Waiting twenty-four or forty-eight hours for a clearly attractive setup is the correct economic response to the fee structure, not idleness. The repo is named trader-swing. The name already knew this.

Both venues push the same way for different reasons. The fee on Binance makes frequent crypto trading unprofitable. The pattern-day-trader rule on Alpaca makes frequent equity trading impossible below twenty-five thousand dollars. Constraint and instinct point in one direction, which is a sign the design is coherent rather than fighting itself.

Patience has its own failure mode, and the discipline has to ride alongside it. Waiting for clear setups is correct; believing a setup is clear when it is not is how patient traders still lose. Selectivity does not substitute for validation. It only changes the question walk-forward must answer, from does this clear fees at high frequency to do these rare high-conviction signals actually predict the move they claim. Fewer trades also means less data to prove skill, which is why a stricter threshold applies when a setup has fewer trades to learn from.

#### The holding period decision

The hold period is upstream of almost everything else. It sets which ATR band makes sense, how often the bot trades, how hard fees bite, how much attention it needs, and which signals mean anything. It is one question: how long do you give a trade to work before you are out with profit or out with a loss.

The spectrum, fast to slow. Scalping, seconds to minutes, is dead for this account: at a 0.2 percent round trip the moves are too small to clear cost and it demands constant attention. Day trading, minutes to hours closed out same day, is attention-heavy, fee-sensitive, and legally blocked on the Alpaca side by the pattern-day-trader rule at this account size. Swing trading, days to a couple of weeks, holds through the noise for a larger, cleaner move; fees become trivial and it needs checking once or twice a day. Position trading, weeks to months, is closer to investing and driven by thesis rather than the technical signals this model is built from, which underuses the machinery already built.

Swing is the band, and the gut answer of one to three days landed inside it. The open question is where inside the band to settle: the tight end, one to three days, or the loose end, up to a week or two. Three things push toward the longer end. Attention, since longer holds need less watching and the operator wants to read the market broadly. Cost, since a small account needs low trade frequency to keep fees from eating it. Safety, since longer holds let the bot trade calmer, deeper, more liquid coins while the system is still being validated. The one thing pulling shorter is data: more trades mean faster validation, which has real value at a proving stage.

So do not fix a single number. Make the hold period a parameter with a range, say one to ten days, and let walk-forward find where the edge actually lives, the same way it sets the ATR band and the fee floor. What is fixed now is the band, swing and not scalp or position. Where inside it the system settles is a thing to discover, not declare. For coin screening this means do not screen against a rigid one-to-three-day ATR cutoff; screen for the swing band generally, coins liquid enough to trust and lively enough to move a few percent over several days.

---

### 2. Governance Architecture

#### Fences, not guardrails

The right mental model is a fence, not a brake. Fees, position size, stop-loss, take-profit, maximum exposure, maximum trades per day: these are the fences. The model acts freely inside them and cannot cross them. This separates what the model decides from what it is permitted to do. The model proposes; the fences dispose. Critically, the fences are not learned. They are imposed in code, so even a model that has found a way to look good by misbehaving cannot trade outside them. That is the protection against volume-hiding: cap trades per day and per position and the volume trick becomes impossible by construction, not by trust.

#### The three stacked defences against volume-hiding

A model judged on cumulative return can always make its numbers look busier by taking many small trades while fees quietly eat the account and the trade count reads as activity. Three defences stack against that, and together they make the trick impossible by construction: the model cannot trade often, cannot trade thin, and cannot hide the result.

1. The trades-per-day cap. A hard limit on how many trades can exist in a day, set in code. The model cannot churn because it cannot place the orders.
2. The minimum-edge floor. A trade is refused unless its expected net move clears the floor. This limits how thin each trade is allowed to be.
3. Out-of-sample validation. Walk-forward reports only the after-fee result on untouched test segments, so no amount of in-sample churn can flatter the verdict.

The minimum-edge floor is the middle pillar, and naming it that way is what makes it load-bearing rather than decorative.

#### The minimum-edge fee floor

The floor is a margin set deliberately above the breakeven fee line, forbidding trades whose expected gain only just clears the fee. The crypto round trip costs roughly 0.2 percent, so the floor sits well above it, in the region of one and a half to two percent expected move. Everything between the fee waterline and that floor is the zone where fees dominate and a performance-driven model is tempted to churn. The floor fences that zone off.

Two points sharpen it or it will not behave as intended.

It is a fence, not an alarm. An alarm tells you a trade is near the waterline and lets it through; a fence refuses it. For the behaviour in question, the model burying thin trades in volume, an alarm is useless because the model can ring the bell and trade anyway while losses accumulate. The floor must be a hard refusal set in code, not a flag the model can note and override. Keep an optional alarm band just above the fence as early warning, but the fence below it is what protects the account.

It is measured on net, not gross. The rule is estimated move, minus round-trip fee, minus expected slippage, must exceed the floor. A trade projecting one percent gross on Binance is really about 0.8 percent once the round trip is paid, less again after slippage. Checked against gross, the floor lets through trades thinner than they look. Net is the honest waterline, and it sits higher than the raw fee.

Who sets the floor matters most. The floor is set by the operator or fixed outside the model's reach, never tuned by the model itself. A model judged on the results the floor produces would lower the floor to book more wins. It is reviewed weekly by the operator, not learned. The floor also couples to the exit: the take-profit target must sit above the floor, because a take-profit below it is incoherent, aiming to exit at a gain the entry rule calls too thin to take. Floor and take-profit are set together. Set too low, the floor lets churn through; set too high, the model sits on its hands and takes no trades for a month, which can look like success until you notice nothing ever cleared the bar. It is a tuned parameter, reviewed weekly, not a number guessed once.

#### Conservatism set once

The MACD signal-line crossover fires earlier, offers a longer runway, and produces more false starts. The zero-line crossover fires later and confirms more. The operator is drawn to the earlier signal and prone to false starts, and this is one of the few biases where the model protects the operator rather than shares it: the model has no impatience and does whatever the guarded logic specifies. So the fix is not in-the-moment discipline but encoding the choice once, in the threshold and confirmation bars, and then not overriding it live. Guarded crossovers and an epsilon noise band exist precisely to suppress the early false start. The danger is not the model's tendency; it is the operator reaching in to take the early signal the model correctly skipped.

#### Operator cadence

The model trades inside fixed fences all week. The operator reviews and re-sets the fences weekly. Weekly review is where a human belongs: adjusting fences, reading whether the regime changed, deciding whether to widen or tighten, and re-running out-of-sample validation. Intra-trade intervention is where humans do damage, so the weekly cadence is itself a guardrail against operator interference. Operator time is best spent reading the market broadly, learning new corners of it and finding where the clear opportunities are, not obsessing over individual trades and graphs.

#### The Karpathy separation principle

The architecture borrows from Karpathy's autoresearch, a March 2026 repo at 86.7k stars. The idea: give an AI agent a small but real training setup and let it experiment autonomously, modifying code, training, checking if the result improved, keeping or discarding, so you wake to a log of experiments. The agent edits one file, `train.py`. The human edits `program.md`, the Markdown instructions, and never touches the Python. The metric, validation bits per byte, is computed by `prepare.py`, which is explicitly marked do not modify, and every experiment is held to a fixed five-minute budget so all runs are measured the same way.

Three things lift directly into this project.

The single editable file. Decide deliberately which file is the model's to edit and keep that boundary narrow. The strategy logic the model tunes lives in one place; the evaluation, the fee floor, the volatility band, and the guardrails live in files the model does not write to. A small editable surface keeps diffs reviewable.

The experiment log as the artefact you wake to. Every walk-forward iteration writes one line: what parameters were tried, the out-of-sample after-fee result, kept or discarded and why. Not the trades, the experiments. That log is what makes the weekly review minutes instead of hours and what catches a model drifting where it should not. Build the logging in from the start.

The frozen yardstick. Hold the evaluation constant: same out-of-sample windows, same fee assumptions, same regime set, across every version of the model. If the yardstick moves, keep-or-discard decisions become noise. Any change to the harness itself is a deliberate human act, recorded separately, never something that happens mid-comparison.

One correction is the more useful half. autoresearch enforces its separation by instruction alone, telling the agent to leave the evaluator alone, which is fine because a coding assistant has no incentive to cheat the metric and a human reviews each morning. This case is harder: the model is optimised against the metric and would profit from gaming it. So the floor and the evals must be enforced by code structure, computed in a layer the model genuinely cannot write to, not merely told not to look at. And autoresearch runs overnight on a GPU where the worst case is a wasted night; this would run on a live account. Trading is adversarial and non-stationary, and a metric stable in-sample can rot out-of-sample in a way a fixed corpus never does. Borrow the separation and the fixed yardstick. Do not borrow the false sense that an autonomous keep-or-discard loop is safe to run unsupervised on live money. The weekly human review is the thing standing between the model and the capital.

---

### 3. The Numbers

#### The fee asymmetry across venues

The cost picture is a clean asymmetry, and it should sit at the top of the arithmetic. On Binance crypto the fee is the binding fence. On Alpaca equities the fee essentially vanishes and a regulatory rule binds instead. The model needs two fence sets and must know which one governs the order it is about to place.

Binance crypto. Spot trading is 0.1 percent per side for regular users, dropping to 0.075 percent if fees are paid in BNB. A round trip is two sides: roughly 0.2 percent standard, 0.15 percent in BNB, every time the bot enters and exits. That breakeven is what separates a real signal from churn, and the 25 percent BNB discount is free money against a fee-sensitive strategy, so keep a BNB balance topped up. Everything else in the fee documents, deposits, withdrawals, promotions, is irrelevant to a bot that holds USDT and trades spot pairs.

Alpaca equities. US stocks and ETFs are effectively commission-free for a direct self-directed API account; Alpaca pays the clearing fees. What remains are regulatory pass-throughs on sells only, and they are tiny: the SEC fee is about 20.60 dollars per million dollars of principal, the FINRA activity fee roughly 0.0002 dollars per share capped low, the CAT fee fractions of a cent per share. On a few-thousand-dollar sale these total cents. For practical purposes the equities side has no per-trade cost worth modelling.

Two cautions on the Alpaca side. First, the commission-free claim holds only for a direct, self-directed cash account; the brokerage schedule's zero-to-three-percent commission band attaches to accounts opened through an authorised business partner or using the Elite Smart Router. Confirm the account is direct self-directed, because the whole equities cost assumption depends on it, and keep the cadence genuinely retail in character, which the patient strategy already does. Second, two costs bite a swing strategy specifically: margin lending runs 6.25 percent annualized on the daily balance, so any leveraged overnight hold quietly erodes a multi-day position, and the outgoing wire is 25 dollars. Trade cash-only and neither margin interest nor a second layer of pattern-day-trader complexity applies. Decide it explicitly: cash account, no margin.

The binding fence on Alpaca equities is therefore not cost but the pattern-day-trader rule, which caps a sub-25k cash account at three day-trades per rolling five days. At this account size that rule forces the patient multi-day hold already preferred. The one number still missing across all the fee documents is the Alpaca crypto commission; until it is in hand the crypto-side breakeven on Alpaca is undefined.

#### The ATR volatility band

The volatility filter uses ATR, average true range, read as a percentage of current price so coins are comparable. ATR is the coin's typical movement over one period, a single day here, averaged across the last fourteen days. It answers how much this coin usually moves in a day right now, not across its whole history. A coin with 3 percent daily ATR typically swings about 3 percent in a day. Because it captures the full range including gaps, and because crypto trades twenty-four seven with no overnight session gaps, daily ATR is actually cleaner in crypto than in equities.

It is a band with two edges, both fitted by walk-forward, both held outside the model's reach.

The floor. A coin must move enough per day to reach the take-profit inside the hold window. If the edge floor is around two percent net over a one-to-three-day hold, a coin whose daily ATR is half a percent simply cannot get there. So daily ATR percent must sit comfortably above the net edge floor, above roughly two to three percent if the edge floor is two percent. This is where the volatility instinct becomes a real filter: it is the number that says how big is big enough to bother.

The ceiling. Above some level, volatility stops being opportunity and becomes unforecastable chaos. Past a certain ATR the coin gaps through stop and take-profit unpredictably, slippage widens, and the indicators lose meaning because price is thrown around by single events rather than tradable structure. The ceiling sits below where the coin detonates, which on crypto is often the high-ATR meme and micro names, frequently ten percent-plus daily ranges. The tradable band for a patient swing strategy lives in the middle: liquid majors and established alts that move a few percent a day reliably without detonating.

No honest exact cutoffs exist in the abstract; distrust anyone who recites them. The right floor and ceiling depend on the edge floor, the hold length, the stop width, and the fee. They are parameters fit by walk-forward across regimes, picking the band that actually produced edge after fees, not numbers chosen from a feeling. And the band must sit outside the model's self-evaluation, the same as the fee floor, because a model rewarded for activity would widen its own ceiling to justify more trades.

The band has two distinct jobs that are easy to conflate. As a selection filter it is the gate that admits or rejects a coin from the universe before the model ever sees it. As a live guardrail it keeps the model from trading a coin that has drifted out of the tradable band. Same metric, two jobs. The ATR band is genuinely missing from the current `day-metrics.ipynb`, which has Kalman, Bollinger, Ichimoku, AMAT, RSI, choppiness, MACD, and the four-vote system but no ATR and no volatility band. It is a concrete build item, not a principle already coded.

#### Hold period and ATR are one dial

Hold period and ATR are locked together. Hold one to three days and the coin must move enough in one to three days to reach the target, so it needs a higher daily ATR. Give a trade up to two weeks and a calmer coin can still get there because it has more days to accumulate the move, so a lower daily ATR is acceptable. Shorter holds demand more daily volatility; longer holds tolerate less. The worry that a quiet coin will miss a one-to-three-day target is exactly right, and the lever that fixes it is either pick livelier coins or lengthen the hold. They are the same dial seen from two ends. The band couples to the edge floor and take-profit as one system: edge floor below take-profit, and ATR floor above the move needed to reach take-profit.

#### Account size sets position count and the ceiling

Position size quietly sets one edge of the volatility band and the number of positions worth holding. At five hundred to a thousand dollars the small size is freeing in one way and constraining in another.

It relaxes the ceiling. Orders this small will not move even a modest order book, so slippage and depth stop constraining the bot, and higher-ATR coins become tradable that could not be touched at fifty thousand because the order is a rounding error in the book. The constraint that bites instead is minimum order sizes and fee granularity. Binance has minimum notional sizes, often low single-digit dollars, and on a small account split across positions, tiny clips bump into those minimums and waste edge on fees. So fewer, slightly larger positions beat many tiny ones, not for strategy reasons but for arithmetic.

Position count lands at three or four open positions maximum at this size, below the usual three-to-six, because anything smaller cannot clear minimums and fees cleanly. The scanned universe can still be fifteen to twenty-five coins. Scan wide, hold few, and few is even fewer than usual because the account is small. That cap is itself a guardrail, the same family as trades-per-day. As the account grows toward five thousand, depth and day-trade constraints re-tighten, which is the point to revisit position count and the volatility band. Build them as parameters, not assumptions, and growth will not force a redesign.

---

### 4. Coin Universe and the Screen

#### Train universe vs scan universe

The resolution to how many coins is not a point between ten and five hundred. It is to separate two things currently treated as one: the universe the model trains on and the universe it trades on.

Training on hundreds of coins because Binance lists them inherits two problems. Most small or new coins are noise driven by illiquidity, single whales, and pump-and-dump mechanics, so feeding them in teaches the model to fit randomness, which is overfitting dressed as coverage. And most of that universe cannot be traded well; thin books mean slippage eats the edge and the backtest lies by assuming fills you would never get. Training on ten high-volume coins picked by one day's volume is the opposite failure: an arbitrary sample with survivorship and recency bias baked in, too few to generalise, a snapshot of one news cycle.

So train on a curated, liquid, reasonably stable set, large enough to span regimes but filtered hard for tradability, something like the top thirty to fifty coins by sustained volume and order-book depth over a trailing window, not a single day. The model learns general microstructure from this clean set. Then, at inference, scan wide: point the trained model at a broader watchlist of fifteen to twenty-five candidates and let it score them, with liquidity as a hard gate before any trade. The wide net catches candidates; the clean-trained model judges them; the liquidity gate stops action on coins that cannot be exited. Selection criteria matter far more than the number, so the notes record the criteria, not a target N.

One venue constraint decides the list. Alpaca and Binance are different universes with different available coins, fees, and data granularity, and Alpaca's crypto offering is much narrower than Binance. Training on Binance-only coins that Alpaca does not list is wasted if the bot trades Alpaca. The training universe has to intersect with what each venue can actually execute, so pin down the execution venue before finalising the coin list.

#### Tradability and regime diversity

Tradability is whether you can get in and out at the price you see, in the size you want, without your own order moving the market. Three things determine it: liquidity, meaning sustained real volume and a deep book; spread, the bid-ask gap that taxes every round trip; and slippage, how far price moves between decision and fill. A coin can print a clean ten percent move on the chart that you could never have captured at size on a thin book. Tradability separates what looks profitable in a backtest from what is profitable when real money hits the book.

Regime diversity is whether the training data contains every market state the model will face: trending up, trending down, ranging sideways, low-volatility grind, high-volatility panic. A model trained only on a bull stretch learns that dips get bought, then gets destroyed the first time the market ranges or sells off because it has never seen that state and confidently does the wrong thing. This is why a single day's top-volume snapshot is dangerous, and why the training window must be long enough and the coin set varied enough to have seen bull, bear, chop, calm, and panic, ideally several of each. Survivorship sanity belongs here too: pick coins that were liquid across the whole training window, not just liquid today.

Two unorthodox ideas are real but belong as separate, individually tested modules on top of a conventionally trained core, on liquid coins only. Whale behaviour splits in two: structural accumulation or distribution on a deep coin leaves learnable footprints in order flow and is signal; single-actor manipulation on a thin microcap is one wallet's whim and is not learnable, it looks like signal right up until it ruins you. The distinction is liquidity, so build whale detection on liquid coins where the footprint is a pattern. Event-driven trading on news or social catalysts is legitimate but a sensing problem more than a price-pattern one; it needs a fast feed and low latency because by the time a move shows on the chart the edge is mostly gone. Flag it as a separate track the price-trained model will not pick up on its own.

Emotive coin selection is the trap to avoid. Interest in what a coin aspires to be, the DeFi and decentralisation thesis, is a claim about long-term value. A one-to-three-day model trades order flow and microstructure, where narrative does not move the next candle. Passion and politics may explain why a coin has sustained community and volume, which helps liquidity, but the model should care whether a coin is liquid and exhibits learnable structure, not whether its mission excites you. Let conviction shape the reading watchlist that feeds candidates into the funnel; make tradability the hard filter on top. The conventional approach is not the boring opposite of instinct, it is the discipline that lets instinct pay off.

#### The four-gate screening function

The concrete front door to everything above is one screening function that takes a coin and returns pass or fail with numbers attached. Inputs per coin come from CCXT OHLCV: fetch the last 90 to 180 daily candles and compute four numbers tested against four gates.

1. Liquidity, a hard gate computed first. 24-hour quote volume in USDT, straight from the ticker. Set a floor in the order of tens of millions in daily USDT volume to stay in genuinely liquid names. Below the floor, reject immediately and compute nothing else.
2. Volatility, the ATR band. Compute 14-day ATR, divide by current price for ATR percent, and test against a floor and a ceiling. The floor is tied to the edge requirement so a normal multi-day move can reach the target; the ceiling rejects the detonating names. Both thresholds are parameters, not hard-coded, so walk-forward can tune them.
3. Spread, a hard gate. Pull best bid and ask from the order book and compute the percentage gap. This is the per-trade tax; reject anything wide. The threshold sits well under the fee.
4. History sufficiency. Count how many candles actually returned. A coin with too few days cannot have lived through multiple regimes and its indicators are unreliable, so reject below a minimum candle count. This is the same skip-too-new logic the day-metrics document already uses.

The output is, per coin, the four raw numbers plus a single pass or fail, where pass means all four gates cleared. Run it across the Binance USDT universe, collect the results in a table of coin, volume, ATR percent, spread percent, candle count, pass or fail, and what survives is the candidate universe. Read the table, eyeball the survivors, pick the fifteen to twenty-five to scan.

Two design notes matter more than the thresholds. Every number lives in one config block, not scattered through the code: the volume floor, the ATR floor and ceiling, the spread limit, the minimum history, all passed in as parameters. This is the `program.md` principle applied to screening: the human owns these numbers, they are visible and tunable in one place, and later they are what walk-forward optimises and what stays outside the model's reach. And the screen runs as a scheduled job, weekly, not once: liquidity and volatility drift, so a coin that passes today may fail in a month. Each run's table, dated and saved, becomes part of the experiment log, the Karpathy artefact you wake to.

One caution closes it. CCXT offering 205 exchanges is power but also a trap. Do not scan all of them; most carry thin, duplicated, or unreliable listings where breadth is noise. Screen within the venue you actually execute on, Binance, so that a coin passing the screen is a coin you can really trade. The wide library is for flexibility in which venue, not for casting a net across all of them at once. The screen is small enough to build quickly and it is the concrete front door to everything else in the manifesto.

---

### 5. Build Sequence and Open Questions

#### First milestone

Before widening the universe or building any submodule, walk-forward must show the existing four-vote model clears fees out-of-sample across bull, bear, and sideways regimes, with a stop and take-profit added. The honest reading of the prior work is that the engine has no demonstrated edge yet: it lost money on every coin in the cynicism check, losing less than buy-and-hold only because sitting flat during a downtrend avoids the fall, which is a drawdown-reduction property, not an edge, confirmed by win rates of 20 to 50 percent. That check ran on hourly bars over forty-one days of a single downtrend and traded only three to seven times per coin, which is already selective, so the failure was not frequency but signals with no demonstrated edge.

The prescription is the real content of chapter two: roll through history, tune weights and threshold on a training segment, score once on an untouched test segment, move forward, repeat, and report only the out-of-sample, after-fee, multi-regime aggregate. Training the model is not the hard part. Proving the trained model has edge that survives fees and out-of-sample testing is, and it is the only thing that justifies going live. If it cannot beat buy-and-hold and a coin flip on the coins already in hand, more coins will not save it; they will hide the failure under volume.

Two concrete things follow, both driven by the fee number. The 2-of-4 threshold and guarded crossovers exist to cut trade frequency, and at 0.15 to 0.2 percent per round trip that frequency control is cost control, so fees belong inside the objective the threshold is tuned against, not bolted on after. And the stop and take-profit the day-metrics document flags as missing are what turn a flat-long rule into something with real risk control; a take-profit set below roughly twice the round-trip cost is mathematically dead on arrival.

#### Submodules to prove or kill

Only after the core clears, build the unorthodox pieces as separate, individually tested modules on top of the conventionally trained base, on liquid coins only. Whale detection on deep coins where accumulation and distribution leave learnable footprints. Event-driven trading on a fast news or social feed as its own track with its own latency requirements. Each is proven or killed on its own evidence rather than quietly contaminating the core.

#### Still open

The candidate coin universe is selected by tradability and regime diversity, not raw count or one day's top volume, and must intersect with what the execution venue can actually trade. Four numbers remain to nail down. The Alpaca crypto commission, the last figure missing from the fee picture. The Alpaca account type, which must be confirmed direct self-directed and cash-only. The exact hold length within the one-to-ten-day band, which walk-forward decides. And the ATR floor and ceiling, which walk-forward also decides. Everything fixed now is a band or a criterion; everything inside is a thing to discover from the data, not declare.

#### The division of labour

The whole architecture exists so the operator does not have to sit over the numbers. The fences hold the model, the weekly review holds the fences, and that frees the operator to do the part that actually has edge and is worth enjoying: reading the market broadly, learning new corners of it, finding where the clear setups live. The bot grinds the trades. The operator ranges across the market. The design is built so that division holds.
