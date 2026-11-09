// Shiny's busy indicators, switched on as Shiny 1.8.0's shiny.ui.busy_indicators.use() does, but
// from a file: Shiny writes these two lines as an inline script, which the CSP's script-src
// 'self' blocks (spec §6.3). src/vid2sub/web/server.py puts this file in that script's place.
document.documentElement.dataset.shinyBusySpinners = true;
document.documentElement.dataset.shinyBusyPulse = true;
