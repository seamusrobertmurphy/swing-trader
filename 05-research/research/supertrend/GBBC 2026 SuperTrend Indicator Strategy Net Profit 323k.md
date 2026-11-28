// © The Good, the Bad and the Bitcoin
//@version=6

indicator("Modern Adaptive Supertrend [GBB]", overlay = true, max_labels_count = 100)

tfSec = timeframe.in_seconds()

// ----------------------------------------------------------------------------
// Mode
//   Modern (auto): TF-aware confluence preset. L2(percentile)+L3 at <=1h where
//     whipsaw dominates; L3 only above 1h where trends are cleaner. L1 stays an
//     experimental opt-in (it did not earn its place OOS).
//   Classic: textbook Supertrend, bar-for-bar (all layers off).
//   Custom: drive each layer from its own toggle (for ablation / power users).
// ----------------------------------------------------------------------------
gMode = "Mode"
preset = input.string("Modern (auto, TF-aware)", "Preset", options = ["Modern (auto, TF-aware)", "Classic (textbook)", "Custom"], group = gMode, tooltip = "Modern auto-tunes per timeframe. Classic = textbook. Custom = use the layer toggles.")

// ----------------------------------------------------------------------------
// Inputs
// ----------------------------------------------------------------------------
gBase = "Base (L0)"
atrPeriodInput = input.int(10, "ATR Period (L0 fallback)", minval = 1, group = gBase, tooltip = "Used when Adaptive Period (L1) is off.")
multInput      = input.float(3.0, "Multiplier (L0 fallback)", minval = 0.1, step = 0.1, group = gBase, tooltip = "Used when Regime Multiplier (L2) is off.")

gL1 = "L1 - Adaptive ATR period (experimental; Custom mode only)"
useL1c    = input.bool(false, "Enable adaptive period", group = gL1, tooltip = "Ehlers homodyne dominant cycle. Off by default: did not earn its place OOS (on 1h BTC the cycle is near-stable, so it just runs slower than fixed-10). Only active in Custom mode.")
minPeriod = input.int(5,  "Min period", minval = 2, group = gL1)
maxPeriod = input.int(50, "Max period", minval = 3, group = gL1)

gL2 = "L2 - Regime-scaled multiplier"
useL2c      = input.bool(false, "Enable regime multiplier (Custom)", group = gL2, tooltip = "Convex KER hinge. In Modern mode this auto-enables at <=1h. Only this toggle applies in Custom mode.")
kerLen      = input.int(20, "KER lookback", minval = 2, group = gL2)
kerPctileIn = input.bool(true, "Rank KER vs its own distribution", group = gL2, tooltip = "Recommended: raw KER on crypto sits below the pivot almost always, collapsing the hinge to a constant wide band. Modern mode forces this on.")
kerPctWin   = input.int(500, "KER percentile window", minval = 20, group = gL2)
pivot       = input.float(0.5, "Hinge pivot", minval = 0.05, maxval = 0.95, step = 0.05, group = gL2)
trendGain   = input.float(0.8, "Trend gain", minval = 0.0, step = 0.1, group = gL2)
chopGain    = input.float(0.5, "Chop gain",  minval = 0.0, step = 0.1, group = gL2)
multMin     = input.float(1.0, "Mult min", minval = 0.1, step = 0.1, group = gL2)
multMax     = input.float(6.0, "Mult max", minval = 0.1, step = 0.1, group = gL2)

gL3 = "L3 - Hysteresis flip filter"
useL3c   = input.bool(true, "Enable hysteresis (Custom)", group = gL3, tooltip = "In Modern mode this is always on. Only this toggle applies in Custom mode.")
hystAtr  = input.float(0.5, "Penetration buffer (xATR)", minval = 0.0, step = 0.1, group = gL3, tooltip = "Close must clear the opposing band by this many ATRs to flip.")
hystBars = input.int(1, "Persistence bars", minval = 0, group = gL3, tooltip = "Penetration must hold this many confirmed bars. 0 = buffer only.")

// --- Preset resolution -------------------------------------------------------
isModern  = preset == "Modern (auto, TF-aware)"
isCustom  = preset == "Custom"
useL1 = isCustom and useL1c
useL2 = isModern ? (tfSec <= 3600) : (isCustom and useL2c)   // L2 only <=1h in Modern
useL3 = isModern ? true            : (isCustom and useL3c)
kerPctile = isModern ? true : kerPctileIn

gDisp = "Display"
showLabel = input.bool(false, "Show regime readout", group = gDisp, tooltip = "Off by default. The on-chart label showing trend / regime / band state.")
mode      = input.string("Beginner", "Readout mode", options = ["Beginner", "Pro"], group = gDisp, tooltip = "Only applies when the regime readout is shown.")
showFill  = input.bool(true, "Fill price to line", group = gDisp)
showFlips = input.bool(true, "Flip markers", group = gDisp)
txtSize   = input.string("Normal", "UI text size", options = ["Small", "Normal", "Large"], group = gDisp)


src = hl2
var float period = 0.0
var float smoothPeriod = 0.0

quad(s, pPrev) => (0.0962 * s + 0.5769 * s[2] - 0.5769 * s[4] - 0.0962 * s[6]) * (0.075 * pPrev + 0.54)

smooth    = (4 * src + 3 * src[1] + 2 * src[2] + src[3]) / 10.0
detrender = quad(smooth, nz(period[1]))
q1        = quad(detrender, nz(period[1]))
i1        = detrender[3]
jI        = quad(i1, nz(period[1]))
jQ        = quad(q1, nz(period[1]))
i2raw     = i1 - jQ
q2raw     = q1 + jI
var float i2 = 0.0
var float q2 = 0.0
i2 := 0.2 * i2raw + 0.8 * nz(i2[1])
q2 := 0.2 * q2raw + 0.8 * nz(q2[1])
reRaw = i2 * nz(i2[1]) + q2 * nz(q2[1])
imRaw = i2 * nz(q2[1]) - q2 * nz(i2[1])
var float re = 0.0
var float im = 0.0
re := 0.2 * reRaw + 0.8 * nz(re[1])
im := 0.2 * imRaw + 0.8 * nz(im[1])
float pRaw = (im != 0.0 and re != 0.0) ? 360.0 / math.todegrees(math.atan(im / re)) : nz(period[1])
pPrev = nz(period[1])
pLim  = pPrev > 0 ? math.max(math.min(pRaw, 1.5 * pPrev), 0.67 * pPrev) : pRaw
pClamp = math.min(math.max(pLim, 6.0), 50.0)
period := 0.2 * pClamp + 0.8 * pPrev
smoothPeriod := bar_index < 1 ? period : 0.33 * period + 0.67 * nz(smoothPeriod[1])

// Clamp + round the adaptive period; fall back to the fixed base period early.
adaptPeriod = math.min(math.max(math.round(smoothPeriod), minPeriod), maxPeriod)
periodUsed  = useL1 and bar_index >= 6 ? adaptPeriod : atrPeriodInput

// ----------------------------------------------------------------------------
// ATR - fixed (ta.atr) or adaptive (hand-rolled Wilder, per-bar alpha).
//   NOTE: ta.rma cannot take a series length, so the adaptive ATR is a manual
//   Wilder recursion atr := atr[1] + (1/len)*(tr - atr[1]). Seeded with the
//   fixed ATR so the two paths agree at the seam.
// ----------------------------------------------------------------------------
tr = ta.tr(true)
atrFixed = ta.atr(atrPeriodInput)
var float atrAdaptive = na
atrAdaptive := na(atrAdaptive[1]) ? atrFixed : atrAdaptive[1] + (1.0 / periodUsed) * (tr - atrAdaptive[1])
atr = useL1 ? atrAdaptive : atrFixed

// ----------------------------------------------------------------------------
// L2 - regime-scaled multiplier (convex hinge on KER)
// ----------------------------------------------------------------------------
kerDir = math.abs(close - close[kerLen])
kerVol = math.sum(math.abs(close - close[1]), kerLen)
ker    = kerVol > 0 ? kerDir / kerVol : 0.0
// Optional percentile rank of KER vs its own rolling window.
kerRank = ta.percentrank(ker, kerPctWin) / 100.0
kerSig  = kerPctile ? kerRank : ker
fTrend  = math.max(0.0, (kerSig - pivot) / (1.0 - pivot))
fChop   = math.max(0.0, (pivot - kerSig) / pivot)
multHinge = multInput * (1.0 + trendGain * fTrend + chopGain * fChop)
multEff   = useL2 ? math.min(math.max(multHinge, multMin), multMax) : multInput

// ----------------------------------------------------------------------------
// Bands + direction (shared L0 math). L3 only gates the flip.
// ----------------------------------------------------------------------------
upperBasic = hl2 + multEff * atr
lowerBasic = hl2 - multEff * atr

var float upperBand = na
var float lowerBand = na
var int   dir = 1
var int   candDir = 0
var int   candCount = 0

ubPrev = nz(upperBand[1], upperBasic)
lbPrev = nz(lowerBand[1], lowerBasic)
upperBand := (upperBasic < ubPrev or close[1] > ubPrev) ? upperBasic : ubPrev
lowerBand := (lowerBasic > lbPrev or close[1] < lbPrev) ? lowerBasic : lbPrev

prevDir = nz(dir[1], 1)
int newDir = prevDir
if not useL3
    newDir := close > ubPrev ? 1 : close < lbPrev ? -1 : prevDir
else
    buf = hystAtr * atr
    if prevDir == 1
        if close < lbPrev - buf
            candCount := candDir == -1 ? candCount + 1 : 1
            candDir := -1
            if candCount >= hystBars
                newDir := -1
                candDir := 0
                candCount := 0
        else
            candDir := 0
            candCount := 0
    else
        if close > ubPrev + buf
            candCount := candDir == 1 ? candCount + 1 : 1
            candDir := 1
            if candCount >= hystBars
                newDir := 1
                candDir := 0
                candCount := 0
        else
            candDir := 0
            candCount := 0
dir := newDir

float supertrend = dir == 1 ? lowerBand : upperBand
flip = dir != prevDir

// ----------------------------------------------------------------------------
// Display
// ----------------------------------------------------------------------------
upCol   = color.new(color.teal, 0)
downCol = color.new(color.red, 0)
stCol   = dir == 1 ? upCol : downCol

stPlot   = plot(supertrend, "Supertrend", color = stCol, linewidth = 2, style = plot.style_linebr)
priceAnchor = plot(close, "", color = color.new(color.gray, 100))   // scale anchor; not display.none
fill(priceAnchor, stPlot, color = showFill ? color.new(stCol, 88) : na)

plotshape(showFlips and flip and dir == 1  ? supertrend : na, "Flip Up",   style = shape.triangleup,   location = location.absolute, color = upCol,   size = size.tiny)
plotshape(showFlips and flip and dir == -1 ? supertrend : na, "Flip Down", style = shape.triangledown, location = location.absolute, color = downCol, size = size.tiny)

// Regime readout (Beginner = plain language, Pro = raw numbers).
tSize = txtSize == "Small" ? size.small : txtSize == "Large" ? size.large : size.normal
atrRank = ta.percentrank(atr, 100) / 100.0
trendingTxt = kerSig >= pivot ? "strong / wide for trend hold" : "weak / wide to suppress whipsaw"
quadrant = (kerSig >= pivot and atrRank >= 0.5) ? "strong trend, high vol" : (kerSig >= pivot ? "quiet trend" : (atrRank >= 0.5 ? "volatile chop" : "quiet chop"))
dirTxt = dir == 1 ? "UP" : "DOWN"

var label tag = na
if barstate.islast and showLabel
    label.delete(tag)
    txt = mode == "Beginner" ? "Trend: " + dirTxt + "\nRegime: " + quadrant + "\nBand: " + trendingTxt : "Dir: " + dirTxt + "  KER: " + str.tostring(kerSig, "#.00") + "\nMult: " + str.tostring(multEff, "#.00") + "  Period: " + str.tostring(periodUsed, "#") + "\nATR%ile: " + str.tostring(atrRank, "#.00") + (useL3 ? "  L3:on" : "  L3:off")
    tag := label.new(bar_index, supertrend, txt, style = dir == 1 ? label.style_label_up : label.style_label_down, color = color.new(stCol, 20), textcolor = color.white, size = tSize)

// ----------------------------------------------------------------------------
// Alerts (named conditions, per the OIPQ pattern) + optional JSON payload.
// ----------------------------------------------------------------------------
alertcondition(flip and dir == 1,  "Flip to uptrend",   "Modern Supertrend flipped UP")
alertcondition(flip and dir == -1, "Flip to downtrend", "Modern Supertrend flipped DOWN")
if flip
    payload = '{"indicator":"ModernSupertrend","dir":"' + dirTxt + '","price":' + str.tostring(close) + ',"ker":' + str.tostring(kerSig, "#.000") + ',"mult":' + str.tostring(multEff, "#.00") + '}'
    alert(payload, alert.freq_once_per_bar_close)


Chapter 1: Introduction to Supertrend Indicator
0:00Super Trend. It is one of the most popular old indicators out there that you can find on every charting platform
0:077 secondsand for good reason because it beautifully displays if the markets are currently in an up or downtrend.
0:1414 secondsHowever, as with most older indicators, it tries to use one setting for every market regime and often totally fails,
0:2222 secondsespecially in choppy markets. So, I thought it's about time to give this indicator a complete overhaul. In this video, I will talk about the following.
0:3131 secondsI will explain what the classic super trend is and what the three structural weaknesses are. The three layers I try
0:3939 secondsto implement to get rid of these weaknesses. How the indicator settings works. How to use the indicator for trading. And finally, why also my
0:4848 secondsversion of super trend is not a crystal ball but a tool for confluence.
0:5353 secondsAs with most of my indicators, my modern adaptive super trend is 100% free and open source available for you on Trading
1:011 minute, 1 secondView. You will find a link in the description and pin comment of this video. All I ask in return is that you leave me a like, subscribe to my
1:101 minute, 10 secondschannel, and especially leave a little comment underneath the video so the YouTube algorithm can continue to work its magic. Thank you. I very much
1:181 minute, 18 secondsappreciate your support. At its core, super trend is a volatilitybased trailing stop. It measures how the
Chapter 2: Why Supertrend Became So Popular
1:251 minute, 25 secondsmarket is moving around using something called average true range or short ATR.
1:321 minute, 32 secondsThen it draws a line that distance away from price. When price is above the line, the line sits underneath in green
1:391 minute, 39 secondsand it is calling an uptrend. When price closes below, the line jumps above price, turns red and it is calling a
1:461 minute, 46 secondsdowntrend. So, it basically just tries to answer one simple question. Are we trending up or down right now? And that
1:551 minute, 55 secondssimplicity is exactly why it got so popular. Think about what it gives you.
2:002 minutesIt is a visual. You can read it in half a second. It works on any market and any time frame. It has basically one setting
2:082 minutes, 8 secondsmost people never touch. And it never leaves you guessing about its bias, green or red, up or down. For a tool
2:142 minutes, 14 secondsthat takes 10 seconds to understand, that's a lot of value. So, no surprise it ended up on millions of charts. But
2:222 minutes, 22 secondsthe same simplicity that made it popular is also where the problems live. There are three structural weaknesses and once you see them, you cannot unsee them.
Chapter 3: Three Structural Weaknesses Explained
2:332 minutes, 33 secondsOne, the distance never changes. The line always sits at the same number of ATRs away from price, no matter what the
2:412 minutes, 41 secondsmarket is doing. A strong clean trend and a messy sideways move get treated exactly the same. In a trend, the
2:492 minutes, 49 secondsdistance can be too tight and kick you out early. In choppy markets, it becomes basically useless as it cannot identify
2:562 minutes, 56 secondsa ranging market. Two, the speed never changes. It reacts at one fixed pace whenever the market is fast or slow. It
3:053 minutes, 5 secondscannot tell the difference. Three, and this is the big one. It flips on a single touch. One wick through the line
3:123 minutes, 12 secondsand the trend flips. Then the next bar flips it back again. That back and forth in the middle of a range is the thing everybody screenshots and complains
3:203 minutes, 20 secondsabout. When it comes to super trend, when you run the classic super trend as always in system, long when it's green,
3:283 minutes, 28 secondsshort when it's red, on the 1 hour and below, it bleeds out. It only holds up at the 4hour and above where the trends
3:353 minutes, 35 secondsare big enough to pay for all these flips.
Chapter 4: Building a Modernized Supertrend Version
3:393 minutes, 39 secondsSo my task when starting to build a modernized version of super trends was simple on paper. Fix the whip saw to make it more stable in ranging markets.
3:493 minutes, 49 secondsI added three layers which each one being optional and I tested each one on its own so I could see exactly what it was contributing to not fool myself.
3:583 minutes, 58 secondsLayer one, the commit filter. This is the one that did most work. It stopped super trend flipping on a single touch.
Chapter 5: Layer One The Commit Filter
4:064 minutes, 6 secondsNow price has to actually commit. It has to close past the line by real margin about half an ATR. Not just tech it and
4:154 minutes, 15 secondsbounce back. That one change cut the false flips by roughly 60%. Same trend read but with far less noise. Layer two,
Chapter 6: Layer Two Adaptive Distance Band
4:244 minutes, 24 secondsthe adaptive distance. I made the bend react to the market instead of sitting at a fixed width. When the market is
4:324 minutes, 32 secondstrending cleanly, the bend moves wider so it holds the move and stops getting shaken out. When the market is chopping
4:394 minutes, 39 secondssideways, it also moves wider because a tight bend in chop is a whipsaw machine.
4:444 minutes, 44 secondsThe only place it tightens up is the transition right when a new move is starting because that is exactly when you want it responsive. and it measures
4:534 minutes, 53 secondstrending versus shopping against the market's own recent behavior, not against a fixed number. So, it can auto
5:015 minutes, 1 secondadapt to the current market regime in a more flexible way. Layer three is the one that caused me the most headache
Chapter 7: Layer Three Adaptive Speed Results
5:085 minutes, 8 secondsbecause it did not work. I also tried making the speed adaptive, letting the look back breathe with the market's
5:165 minutes, 16 secondsrhythm. After I built and tested it, it really didn't add anything on crypto.
5:215 minutes, 21 secondsThe underlying riven turned out to be basically stable. So, Adaptive just gave us a slightly slower copy of the same
5:295 minutes, 29 secondsindicator. It disagreed with the simple version on about 5% of bars and traded no better. I however left it in the
5:375 minutes, 37 secondssettings so you can experiment with it yourself. Maybe you can come up with a solution on how to make it work that I
5:455 minutes, 45 secondsdid not see. Let's look at the difference between the classic super trend and my modern adaptive super trend on this chart. You can see at glance
Chapter 8: Classic vs Modern Supertrend Comparison
5:545 minutes, 54 secondsthat it gives you a much cleaner read of which way the trend is actually pointing. Let me walk you through the settings without drowning you in too
Chapter 9: Indicator Settings and Presets Explained
6:036 minutes, 3 secondsmuch math. The presets switch is the main control. You can get classic, modern, and custom. Classic is the
6:116 minutes, 11 secondstextbook super trend unchanged for comparison. Modern is the default and is the one I recommend to use. Custom is if
6:206 minutes, 20 secondsyou want to turn individual layers on and off yourself.
6:256 minutes, 25 secondsThe modern setting adjusts itself to your time frame, so you do not have to experiment with the settings yourself.
6:326 minutes, 32 secondsOn the 1 hour and below, it runs both the adaptive distance and the commit filter. Above the 1 hour, it runs the
6:406 minutes, 40 secondscommit filter only and drops the adapt adaptive distance. Why? Because at higher time frames, the classical
6:476 minutes, 47 secondsdistance already works fine and the extra layer did not earn its place in testing. So, I took it out there because
6:556 minutes, 55 secondsthis is what the data told me. If you go into custom, the knobs that matters are simple. There's how much wider the band
7:037 minutes, 3 secondsgoes in a trend and how much wider it goes in a shop. There's the commit buffer, how far past the line it has to close before it flips, set to about half
7:127 minutes, 12 secondsan ATR by default. And there's persistence, how many bars it has to hold before the flip counts. The
7:207 minutes, 20 secondsdefaults are what I tested and they generally work well for most assets.
7:257 minutes, 25 secondsDisplay is straightforward. Colored line, an optional fill, and flip markers. There's also an optional regime
Chapter 10: Supertrend Is Not a Trading System
7:327 minutes, 32 secondslabel that shows you what the indicator is thinking, whether it sees trend or chop. That is off by default to keep
7:407 minutes, 40 secondsyour chart clean, but feel free to turn it on if you want more details shared by the indicator. Alerts, you get a flip up
7:477 minutes, 47 secondsalert, a flip down alert, and a web hook option if you want to wire into something automated. One thing I want to be very clear about before you go and
7:567 minutes, 56 secondsstart trading with my modern adaptive super trend. This is not a full trading system. Do not trade just based on what
8:058 minutes, 5 secondsthis indicator tells you. On direction, this indicator is right about 48% of the time, which is basically a coin flip.
8:148 minutes, 14 secondsSuper trend does not predict where price is going. It follows where price has been. The modern version follows it with
8:228 minutes, 22 secondsless noise, but it is not forecasting anything. So, how do you actually use it as one layer of confluence? Let me show
Chapter 11: Using Supertrend as Confluence Layer
8:318 minutes, 31 secondsyou what I mean by this. On this Bitcoin five-minute chart, I am using my modern adaptive super trend, my modern adaptive
8:398 minutes, 39 secondsMACD plus my standard deviation channel for X. All of these are available for free on Trading View. You can find them under scripts on my profile page there.
8:508 minutes, 50 secondsOn June 17th, 2026 at about 6:25, the MACD showed a bearish divergence while
8:588 minutes, 58 secondsprice was was trading around the plus two sigma level of a standard deviation.
9:049 minutes, 4 secondsSo, I placed a market cell with a tight stop just above the last local high and uh a takerit target of 2 R. meaning that
9:149 minutes, 14 secondsshould my take-profit hit, I would earn twice as much as I had to risk. Watch how the market continued after that.
9:239 minutes, 23 secondsSuper trend eventually also flipped to red, confirming that the market bias was dropping towards bearish, which gave me
9:309 minutes, 30 secondsan additional boost in confidence for this trade as three layers of confluence were now aligning. Bearish divergence
9:389 minutes, 38 secondsfrom the MACD. The signal from the MACD being at mathematically important point with plus two sigma of a standard
9:469 minutes, 46 secondsdeviation channel plus eventually super trend also flipping to bearish. A little while later my tech profits was hit.
9:549 minutes, 54 secondsThis is exactly what I mean when I talk about confluence multiple tools lining up and telling you the same story instead of just uh using one tool and
10:0310 minutes, 3 secondshoping that it's the holy grail of trading.
10:0610 minutes, 6 secondsMy suggestion is to experiment a little bit with this indicator and see whether or not it adds a layer of confluence to
Chapter 12: Final Thoughts and Call to Action
10:1410 minutes, 14 secondsyour own trading style as the indicator is open source. Also, feel free to change the code in any way you want to adapt it more to your own trading style.
10:2410 minutes, 24 secondsIf you enjoyed this video, I would appreciate it if you leave me a like and subscribe to my channel. I publish new videos about trading indicators and quantitative trading stuff every week.
10:3610 minutes, 36 secondsSee you in the next video.

Sync to video time
