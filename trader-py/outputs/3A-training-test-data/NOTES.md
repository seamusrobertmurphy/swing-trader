# 3A - Training/test data (walk-forward design)

Chapter Three, Execution. This stage sets the test design for the whole chapter and
builds the data that design cuts. Walk-forward is established here and everything
downstream is judged by it.

## Walk-forward, the test design

Cut each coin's history into rolling segments: a training window, then the next unseen
test window, then slide forward and repeat through the whole history. A gap (embargo)
sits between train and test so a trade or label from the training side cannot leak into
the test side. Every result in Chapter Three is read from the test windows only,
out-of-sample and after fees, across rising, falling, and sideways markets. This is the
rule the rest of the chapter trains and tunes inside.

## The data that gets cut

`inputs/build_dataset.py` builds one row per coin per day across the ten-coin market:
scale-invariant features (so one model works across BTC at $60k and DOGE at $0.20) and
a forward-looking label (1 if the close reaches the target before the stop within the
horizon, else 0). Features use only past data; the forward-looking label is why the last
HORIZON rows of each coin are dropped.

## Scripts and output

- `inputs/walkforward.py` - the walk-forward split design and the exit simulator
- `inputs/build_dataset.py` - the labeled dataset
- `outputs/CSV/dataset.csv` - the data, before splitting

Both scripts stay in `inputs/` until their import and path coupling is hardened (see 3B);
then they fold in here.
