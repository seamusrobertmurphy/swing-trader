panel: 2574 names x 2670 days

PANEL A  liquidity tiers (same 60% fold bars)
    universe  months   top   mkt  spread  tstat abs_rate sel_rate  verdict
  full panel     115 2.215 1.132   1.082   2.53      89%      79% SURVIVES
top-1000 liq     115 2.276 1.070   1.206   2.35      89%      74% SURVIVES
 top-500 liq     115 2.692 1.106   1.586   2.35      89%      79% SURVIVES

PANEL B  adversarial delisting injection into the TOP decile (full panel)
delist_ret monthly_rate annualized  spread  tstat sel_rate holds
      -30%        0.25%         3%   0.861   2.02      74%   YES
      -30%        0.50%         6%   0.841   1.98      74%    no
      -30%        1.00%        12%   0.624   1.47      68%    no
      -55%        0.25%         3%   0.687   1.61      68%    no
      -55%        0.50%         6%   0.651   1.53      68%    no
      -55%        1.00%        12%   0.264   0.62      63%    no

PANEL C  literature anchor: CRSP delisting-complete 12-1 long-only premium is roughly +0.5 to +0.8%/month over the market;
compare the full-panel spread above. Far above that range would itself flag bias.
