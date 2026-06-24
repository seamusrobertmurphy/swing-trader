
super trend is a very versatile
0:02
indicator it can be used in multiple
0:04
ways you can use it inside a strategy as
0:07
a stop-loss or a profit Target or as a
0:10
signal to enter and exit or as a filter
0:14
for another signal and in this video I
0:16
will show you how to build a strategy
0:19
using super Trend as a signal the
0:21
indicator equation is very simple and
0:24
it's very close to Kelner channel so for
0:27
the upper band we use this average and
0:29
add a multiplier of an ATR so in this
0:33
case we have two variables it is the ATR
0:35
look back and the multiplier and then
0:38
same thing for the lower band so it's
0:41
the same average but this time we deduct
0:43
the multiplier times the ATR so it's the
0:46
same equation for Kelner Channel but
0:48
Kelner Channel uses the exponential
0:51
moving average instead of the high plus
0:54
low divide by two the other difference
0:56
from kelon channel is the drawing this
0:59
is the chart of the NASDAQ 100 Futures
1:03
represented by nq. D which is the daily
1:06
session and the indicator plotted is the
1:09
super Trend indicator so like I
1:11
mentioned it has two channels the upper
1:14
Channel which is in red the lower
1:17
Channel which is in green and notably we
1:19
can see the difference from the Kelner
1:22
Channel because we are plotting only one
1:24
at a time so when the price close above
1:28
the upper Channel we draw the lower band
1:33
and when the price close below the lower
1:37
Channel we draw the upper band another
1:41
difference is we only draw the lower
1:44
Channel when we get a higher high so you
1:46
see once we don't get a higher high we
1:49
are flat so again here we are flat again
1:52
here we are flat same thing when we are
1:54
trending down you see when we don't make
1:57
lower low we are flat both of these
2:00
characteristics make the super Trend
2:02
indicator unique so when the trend is up
2:05
it always follows the trend and have a
2:08
flat area if we don't make a higher high
2:11
and when we are trending down it always
2:13
going down and we have a flat area when
2:17
we don't make a lower low and that's why
2:19
we are drawing one band at a time so now
2:21
that we understand how super Trend works
2:23
we can easily build a strategy using the
2:27
super Trend signal and the signal will
2:29
be when the indicator flips from up to
2:32
down and from down to up and since I'm
2:35
testing this on the NASDAQ 100 NASDAQ
2:38
being one of the indexes in the US it
2:41
tends to drift up most of the time so we
2:44
will not use it to build a short
2:46
strategy we will only use the long side
2:49
so our strategy will go long
2:52
whenever this channel flips from red to
2:55
Green basically whenever the price close
2:59
up above the upper Channel and here is
3:01
the strategy applied so you can see
3:03
whenever we flip we buy the next bar and
3:07
whenever we flip on the opposite side we
3:10
sell the next bar and we are going long
3:12
only using a single contract and these
3:15
are the results of the strategy 125
3:17
trades with about 50% win rate and a
3:21
huge huge average trade our return to
3:24
draw down is 2.7 and this is our
3:27
periodical analysis now of course we can
3:30
optimize this so we can optimize the
3:34
length of the ATR from 5 to 30 step five
3:37
and the
3:38
multiplier from 1 to 15 Step One so
3:41
overall 90 combinations and this is the
3:44
result of the optimization sorted by
3:47
return to draw down and we see at the
3:48
top the length is 30 20 and then couple
3:52
of five 25 so it's all over the place
3:55
and this is the 3D
3:57
representation so we can see this area
4:00
is probably stable so between 10 and 12
4:04
on the ATR
4:06
multiplier and 20 to 30 of the length
4:11
now we can see here the problem is the
4:13
low number of Trades very few strategies
4:16
have higher than 100 so this one which
4:20
is the length of the ATR is five and the
4:23
multiplier is two which makes sense
4:25
because that means we are the the
4:27
channel will be very close to the price
4:29
so we get more trades and if I sort by
4:32
the multiplier you can see this is
4:34
number two and all of them producing
4:38
High number of Trades now this is
4:40
totally different than one so one
4:43
producing more trades but you can see
4:45
the results for the one multiplier
4:47
they're all losing money so it's a huge
4:50
jump between one and two where two all
4:52
of them making a lot of money now just
4:55
like a moving average we can use a
4:57
longer length period for the
5:01
ATR and use it with the short period so
5:05
imagine just like the 50-day moving
5:07
average and the 200 day moving average
5:10
so in this case we can use 2 and 10 as
5:14
our entry
5:15
signal while we have a longer ATR period
5:21
also on the long side and this is how it
5:24
looks like on the chart so the bright
5:25
green and red this is our short length
5:29
ATR and multiplier and then the dark
5:33
green and dark red is the longer version
5:35
and you can see in this case this signal
5:38
will not be taken because this one is in
5:42
an uptrend but the longer version is in
5:45
a downtrend so here is our strategy with
5:47
the two super Trend indicators so one is
5:50
fast and one is slow and we are uh
5:54
optimizing the fast one the same as
5:56
before so from 5 to 30 the length in
5:59
step of five
6:00
the multiplier 1 to 15 Step one and then
6:03
the slow length super Trend will be the
6:06
ATR look back is from 40 to 100 step 10
6:11
and the multiplier from 4 to 14 step two
6:14
all in all we have about
6:16
3,700 strategies this is the result of
6:19
the optimization and we can see now we
6:22
have four variables and this will be
6:26
hard to see in a 3D graph because the Y
6:29
AIS is is the net profit and then X and
6:32
Y is two variables and then this is the
6:35
third but we're still missing the fourth
6:37
so you can overcome this by removing one
6:42
of the variables and it's very easy to
6:44
remove one of the variables in this case
6:46
we can just say that whenever we
6:49
optimize the length of the short super
6:52
Trend indicator we use the same value
6:55
times three for the long super trend
6:59
indicator so as you can see now we have
7:02
three variables to optimize so the fast
7:06
length of the ATR same 5 to3 the fast
7:10
length ATR multiplier 1 to 15 that's the
7:13
same and now our slow length is always
7:19
three times this value so when this is
7:22
five the slow length will be 15 when
7:25
this is 10 this slow length will be 30
7:29
and so on so forth and then the slow ATR
7:32
multiplier is the third variable so now
7:35
overall we have 540 combination and this
7:39
is the result and as you can see we have
7:41
three variables so very easy we can
7:43
represent that so you see now this is
7:45
the fast ATR multiple and this is the
7:49
fast ATR length and the slow length is 3
7:53
times this value and the z-axis of
7:56
course is the net profit and now this is
7:58
our third variable so we can see 4 6 8
8:02
10 and all of them look at this all of
8:05
them are very very stable going back to
8:07
the spreadsheet uh we can see again we
8:10
have a problem of Trades so this one is
8:12
100 Trade so if we filter for 100 trades
8:15
and $100 on average per trade we end up
8:19
with only 16 strategies so this is the
8:22
top strategy the ATR length for the fast
8:26
super Trend indicator is 10 the
8:28
multiplier is two and this low super
8:30
Trend indicator has a length of three
8:33
times this so it's 30 and then the
8:36
multiplier is four so this is the result
8:39
of the strategy 191,000 5 to1 return to
8:42
draw down and this is the curve but as
8:46
you can see we have only a 100 trades
8:49
now we can easily overcome the drawback
8:51
of the low number of Trades by switching
8:54
to a lower time frame because with a
8:56
lower time frame of course we will get
8:59
more signals and then we can easily
9:01
filter the extra signals out so let's
9:05
try the strategy on the same Market but
9:08
we will switch to 60 Minutes time frame
9:11
so now we are on the same Market the
9:13
NASDAQ 100 Futures but now we are using
9:16
the 1eh hour time frame and again we
9:19
have the two super Trend indicator so I
9:22
will optimize the fast and slow super
9:25
Trend indicators with the settings that
9:28
gives us in total 2700 combinations and
9:32
this is the result of the optimization
9:34
so out of 2700 strategies we have about
9:38
50% of the strategies that has more than
9:41
100 trades and more than $100 on average
9:44
per trade and as you can see the
9:46
difference is huge when we switch to
9:48
intraday so look at all these number of
9:51
Trades they are 500 400 1,000 so on The
9:54
Daily we were barely making 100 trades
9:57
and here we have so many and the
9:59
advantage here is we can easily now add
10:02
a filter to enhance our strategy now let
10:06
me pick this strategy so this is
10:08
15770 60 about 642 trades with a really
10:13
good average for the NASDAQ 348 so this
10:16
is our strategy performance 223 with 5.1
10:20
return to draw down and these are the
10:22
trade
10:24
results the problem is here is when we
10:26
look at this Equity curve we we can see
10:29
we are in a big draw down for almost 6
10:34
seven years now from experience when you
10:36
see an equity curve like this it's
10:38
usually a direction filter that will fix
10:42
this type of equity curve because
10:44
basically the market regime was in a
10:47
certain type and volatility Market
10:50
regime doesn't stay long enough so
10:53
usually it's a direction Market regime
10:55
now we can easily do this with a 200 day
10:58
moving average so we say only go long
11:02
using whatever combinations of the super
11:04
Trend indicator when the price is above
11:06
the 200 day moving average that works
11:08
really well on the indexes of course
11:11
since we are using the trend filter we
11:14
can introduce another longer version of
11:18
the super Trend indicator so we have the
11:21
short and let's say the medium term and
11:24
then the really really long term that
11:27
will act just like a 200 moving average
11:30
so I will show you both of them and how
11:32
they will affect the strategy so this is
11:35
the equity curve of the two super Trend
11:39
indicators and now I will add the 200
11:43
day moving average meaning we will only
11:45
take the signal when both of them are
11:49
green both the super Trend indicators
11:52
and the price is above the 20 day moving
11:54
average so if we compile and you see how
11:57
we got rid of of all
11:59
that draw down and let's see the
12:02
performance and also we make more money
12:05
our return to draw down goes down a
12:07
little bit we were 5 something and like
12:09
I told you this is the advantage of
12:11
having more trades because you can
12:13
easily add a filter and even after the
12:15
filter we have
12:17
252 trades 62% and we're making about
12:21
$1,200 on average now going back here
12:25
instead of the 200 day moving average I
12:27
will add a longer version of the super
12:30
Trend this time I'm going to use a
12:33
150 bars lookback for the ATR and let's
12:38
see how that's going to affect so it
12:41
looks almost the same let's see the
12:43
performance even though we making same
12:45
money our return to draw down is not as
12:48
good now of course I can fix the let's
12:51
say long-term Trend filter so I can fix
12:54
the super Trend at 150 and now
12:57
reoptimize the
12:59
short and the medium super Trend there
13:02
are many ways to go about this but the
13:04
idea is the same super Trend indicator
13:07
can be used for everything as a filter
13:10
and as an entry signal in fact I don't
13:12
want to complicate things but I can
13:13
still use the same super Trend indicator
13:17
as a stop loss or a profit Target for
13:19
this strategy and it works really well
13:21
because it's a kind of a breakout
13:23
strategy and if you use it as a trailing
13:26
stop it it will protect a lot of of your
13:29
profits and that's why this super Trend
13:31
indicator is really really versatile if
13:34
you like this video then you will love
13:35
the next one
13:39
[Music]