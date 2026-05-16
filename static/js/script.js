/**
 * SeminarFinal_v5.1 - Client JavaScript
 * Production-ready client for real-time stock market simulation.
 */

class StockSimulator {
    constructor() {
        this.socket = null;
        this.activeMode = 'historical';
        this.companyNames = window.companyNames || {};
        this.tickers = window.tickers || [];

        this.djiLabels = [];
        this.djiData = [];
        this.sp500Labels = [];
        this.sp500Data = [];

        this.currentPrices = {};
        this.previousPrices = {};
        this.anchorPrices = {};
        this.lastAnchorPrices = {};
        this.displayPrices = {};
        this.priceAnimationFrame = null;
        this.priceAnimationDuration = 0;
        this.holdings = {};
        this.cash = 0;
        this.tradeTicker = null;

        if (window.startDate) {
            this.checkSP500Availability(window.startDate);
        }
        this.tradeType = null;
        this.tradePrice = 0;
        this.insiderOpportunityAvailable = false;
        this.insiderOpportunityOpen = false;
        this.reubenCelebrated = false;
        this.lastGameDate = null;

        this.init();
    }

    init() {
        this.connectSocket();
        this.initCharts();
        this.bindEvents();
        this.updateModeUI();
    }

    connectSocket() {
        this.socket = io({
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: 5
        });

        this.socket.on('connect', () => {
            console.log('Connected to server');
            console.log('Room code:', window.roomCode, 'Username:', window.username);
            this.socket.emit('join_room', {
                room_code: window.roomCode,
                username: window.username
            });
        });

        this.socket.on('joined_room', (data) => {
            this.tickers = data.tickers || this.tickers;
            this.companyNames = data.company_names || this.companyNames;
            this.updateModeUI();
        });

        this.socket.on('game_state_update', (data) => this.updateGameState(data));
        this.socket.on('game_tick', (data) => this.handleGameTick(data));
        this.socket.on('leaderboard_update', (data) => this.updateLeaderboard(data.leaderboard));
        this.socket.on('portfolio_update', (data) => this.updatePortfolio(data));
        this.socket.on('trade_success', (data) => {
            console.log('Trade success:', data);
            this.showPopup(
                `✅ ${data.action === 'buy' ? 'Bought' : 'Sold'} ${data.ticker}`,
                `${data.action === 'buy' ? 'Bought' : 'Sold'} ${data.shares.toFixed(4)} shares of ${data.ticker} at ${this.formatCurrency(data.price)}\nTotal: ${this.formatCurrency(data.total)}`,
                'success'
            );
        });
        this.socket.on('market_event', (data) => this.handleMarketEvent(data));
        this.socket.on('market_panic', (data) => console.log('Market panic:', data));
        this.socket.on('new_headline', (data) => this.updateHeadlineTicker(data));
        this.socket.on('insider_opportunity', (data) => this.handleInsiderOpportunity(data));
        this.socket.on('insider_rumor', (data) => this.handleInsiderRumor(data));
        this.socket.on('insider_tip', (data) => this.handleInsiderTip(data));
        this.socket.on('insider_status_updated', (data) => this.handleInsiderStatusUpdate(data));
        this.socket.on('sec_penalty', (data) => this.handleSECPenalty(data));
        this.socket.on('game_over', (data) => this.handleGameOver(data));
        this.socket.on('info', (data) => this.showPopup('Notice', data.message));
        this.socket.on('error', (data) => console.error('Server error:', data));

        this.socket.on('connect_error', (error) => {
            console.error('Socket connection error:', error);
        });
    }

    initCharts() {
        if (!window.isAdmin) {
            return;
        }

        const djiCtx = document.getElementById('chart-dji');
        const sp500Ctx = document.getElementById('chart-gspc');
        if (!djiCtx || !sp500Ctx) return;

        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    enabled: true,
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    titleColor: '#e2e8f0',
                    bodyColor: '#94a3b8',
                    borderColor: 'rgba(148, 163, 184, 0.2)',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        label: (context) => `Price: $${context.parsed.y.toFixed(2)}`
                    }
                }
            },
            scales: {
                x: {
                    type: 'category',
                    grid: { color: 'rgba(148, 163, 184, 0.1)' },
                    ticks: {
                        color: '#94a3b8',
                        maxTicksLimit: 8,
                        maxRotation: 45
                    }
                },
                y: {
                    grid: { color: 'rgba(148, 163, 184, 0.1)' },
                    ticks: {
                        color: '#94a3b8',
                        callback: (value) => `$${value.toFixed(0)}`
                    }
                }
            }
        };

        const djiGradient = djiCtx.getContext('2d').createLinearGradient(0, 0, 0, 400);
        djiGradient.addColorStop(0, 'rgba(251, 146, 60, 0.15)');
        djiGradient.addColorStop(1, 'rgba(251, 146, 60, 0)');

        this.djiChart = new Chart(djiCtx.getContext('2d'), {
            type: 'line',
            data: {
                labels: this.djiLabels,
                datasets: [{
                    label: 'Dow Jones',
                    data: this.djiData,
                    borderColor: '#fb923c',
                    backgroundColor: djiGradient,
                    borderWidth: 1.5,
                    fill: true,
                    tension: 0,
                    pointRadius: 0,
                    pointHoverRadius: 6,
                    pointHoverBorderWidth: 2,
                    pointHoverBackgroundColor: '#ffffff',
                    pointHoverBorderColor: '#fb923c'
                }]
            },
            options: chartOptions
        });

        const sp500Gradient = sp500Ctx.getContext('2d').createLinearGradient(0, 0, 0, 400);
        sp500Gradient.addColorStop(0, 'rgba(56, 189, 248, 0.15)');
        sp500Gradient.addColorStop(1, 'rgba(56, 189, 248, 0)');

        this.sp500Chart = new Chart(sp500Ctx.getContext('2d'), {
            type: 'line',
            data: {
                labels: this.sp500Labels,
                datasets: [{
                    label: 'S&P 500',
                    data: this.sp500Data,
                    borderColor: '#38bdf8',
                    backgroundColor: sp500Gradient,
                    borderWidth: 1.5,
                    fill: true,
                    tension: 0,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    pointHoverBorderWidth: 2,
                    pointHoverBackgroundColor: '#ffffff',
                    pointHoverBorderColor: '#38bdf8'
                }]
            },
            options: chartOptions
        });
    }

    bindEvents() {
        document.querySelectorAll('.btn-buy').forEach(btn => {
            if (btn) btn.addEventListener('click', e => this.openTradeModal(e.target.dataset.ticker, 'buy'));
        });
        document.querySelectorAll('.btn-sell').forEach(btn => {
            if (btn) btn.addEventListener('click', e => this.openTradeModal(e.target.dataset.ticker, 'sell'));
        });

        const modalClose = document.getElementById('modal-close');
        if (modalClose) modalClose.addEventListener('click', () => this.closeModal());

        const modalCancel = document.getElementById('modal-cancel');
        if (modalCancel) modalCancel.addEventListener('click', () => this.closeModal());

        const modalConfirm = document.getElementById('modal-confirm');
        if (modalConfirm) modalConfirm.addEventListener('click', () => this.executeTrade());

        const tradeAmount = document.getElementById('trade-amount');
        if (tradeAmount) tradeAmount.addEventListener('input', () => this.updateTradeTotal());

        const insiderButton = document.getElementById('insider-rumor-btn');
        if (insiderButton) {
            insiderButton.addEventListener('click', () => this.requestInsiderRumor());
        }

        const gameOverClose = document.getElementById('game-over-close');
        if (gameOverClose) {
            gameOverClose.addEventListener('click', () => {
                const overlay = document.getElementById('game-over-overlay');
                if (overlay) overlay.classList.remove('visible');
            });
        }

        if (window.isAdmin) {
            const playBtn = document.getElementById('play-pause-btn');
            if (playBtn) playBtn.addEventListener('click', () => this.socket.emit('toggle_game'));
        }

        const tradeModal = document.getElementById('trade-modal');
        if (tradeModal) {
            tradeModal.addEventListener('click', e => {
                if (e.target.id === 'trade-modal') {
                    this.closeModal();
                }
            });
        }
    }

    updateGameState(data) {
        console.log('updateGameState called:', data);
        const displayDate = data.current_date || data.game_date;
        if (displayDate) {
            const dateEl = document.getElementById('current-date');
            if (dateEl) dateEl.textContent = displayDate;
        }

        const statusIndicator = document.getElementById('status-indicator');
        const statusText = document.getElementById('status-text');
        let isPlaying = data.game_state === 'playing';
        if (data.playing !== undefined) {
            isPlaying = data.playing;
        }

        if (statusIndicator) statusIndicator.classList.toggle('playing', isPlaying);
        if (statusText) statusText.textContent = isPlaying ? 'Playing' : 'Paused';
        if (window.isAdmin) {
            const playBtn = document.getElementById('play-pause-btn');
            if (playBtn) playBtn.innerHTML = isPlaying ? '<span class="btn-icon">⏸</span> Pause' : '<span class="btn-icon">▶</span> Play';
        }

        this.tickers = data.tickers || this.tickers;
        this.companyNames = data.company_names || this.companyNames;
        this.updateModeUI();
        this.updateHeadlineTicker(data);
        if (data.insider_opportunity) {
            this.handleInsiderOpportunity(data.insider_opportunity);
        }
        if (data.market_event) {
            this.handleMarketEvent(data.market_event);
        }
        this.handleDateDrivenEvents(data.current_date);

        if (data.prices) {
            this.currentPrices = data.prices;
            this.updatePriceDisplay(data.prices);
        }

        if (!window.isAdmin && data.cash !== undefined) {
            this.updatePortfolio({
                cash: data.cash,
                holdings: data.holdings,
                holdings_value: data.holdings_value,
                net_worth: data.net_worth
            });
        }

        if (data.historical_prices && window.isAdmin) {
            this.populateChartsFromHistorical(data.historical_prices, data.current_date);
        }

        this.animateMarketTo(data.prices || {}, data.tickers || [], data.current_date);
    }

    handleGameTick(data) {
        if (!data) return;
        const dateEl = document.getElementById('current-date');
        if (dateEl && data.game_date) {
            dateEl.textContent = data.game_date;
        }
        if (data.dji_price !== undefined) {
            this.currentPrices['^DJI'] = data.dji_price;
            const el = document.getElementById('price-^DJI');
            if (el) el.textContent = this.formatCurrency(data.dji_price);
        }
        if (data.gspc_price !== undefined && data.game_date >= '1957-03-04') {
            this.currentPrices['^GSPC'] = data.gspc_price;
            const el = document.getElementById('price-^GSPC');
            if (el) el.textContent = this.formatCurrency(data.gspc_price);
        }
        if (window.isAdmin) {
            const djiVal = document.getElementById('dji-value');
            const gspcVal = document.getElementById('sp500-value');
            if (djiVal && data.dji_price !== undefined) djiVal.textContent = this.formatCurrency(data.dji_price);
            if (gspcVal && data.gspc_price !== undefined && data.game_date >= '1957-03-04') gspcVal.textContent = this.formatCurrency(data.gspc_price);
        }
    }

    updatePriceDisplay(prices) {
        for (const [ticker, price] of Object.entries(prices)) {
            const priceEl = document.getElementById(`price-${ticker}`);
            const changeEl = document.getElementById(`change-${ticker}`);
            if (priceEl) {
                priceEl.textContent = this.formatCurrency(price);
            }
            if (changeEl && this.previousPrices[ticker]) {
                const change = ((price - this.previousPrices[ticker]) / this.previousPrices[ticker]) * 100;
                changeEl.textContent = `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`;
                changeEl.className = `price-change ${change >= 0 ? 'positive' : 'negative'}`;
            }
        }
    }

    populateChartsFromHistorical(historicalPrices, currentDate) {
        if (!historicalPrices) return;

        if (historicalPrices['^DJI']) {
            this.djiLabels = Object.keys(historicalPrices['^DJI']).sort();
            this.djiData = this.djiLabels.map(date => historicalPrices['^DJI'][date]);
            if (this.djiChart) {
                this.djiChart.data.labels = this.djiLabels;
                this.djiChart.data.datasets[0].data = this.djiData;
                this.djiChart.update('none');
            }
        }

        if (historicalPrices['^GSPC']) {
            this.sp500Labels = Object.keys(historicalPrices['^GSPC']).sort();
            this.sp500Data = this.sp500Labels.map(date => historicalPrices['^GSPC'][date]);
            if (this.sp500Chart) {
                this.sp500Chart.data.labels = this.sp500Labels;
                this.sp500Chart.data.datasets[0].data = this.sp500Data;
                this.sp500Chart.update('none');
            }
        }
    }

    updatePrices(prices, tickers = []) {
        tickers = tickers.length ? tickers : Object.keys(prices || {});

        document.querySelectorAll('.stock-card').forEach(card => {
            const ticker = card.dataset.ticker;
            const priceEl = card.querySelector('.price');
            const changeEl = card.querySelector('.change');
            const statusEl = card.querySelector('.stock-status');
            const buyBtn = card.querySelector('.btn-buy');
            const sellBtn = card.querySelector('.btn-sell');
            const companyNameEl = card.querySelector('.company-name');
            const visible = tickers.includes(ticker);

            card.style.display = visible ? '' : 'none';
            if (!visible) return;

            const price = prices[ticker];
            const companyName = this.companyNames[ticker] || ticker;
            if (companyNameEl) companyNameEl.textContent = companyName;

            if (price === undefined || price === null) {
                if (priceEl) priceEl.textContent = '--';
                if (changeEl) changeEl.textContent = '';
                if (statusEl) {
                    statusEl.textContent = 'Not yet IPO\'d';
                    statusEl.className = 'stock-status unavailable';
                }
                if (buyBtn) buyBtn.disabled = true;
                if (sellBtn) sellBtn.disabled = true;
                return;
            }

            if (priceEl) {
                const currentPrice = Number(priceEl.textContent.replace(/[$,]/g, '')) || 0;
                if (Math.abs(price - currentPrice) > 0.01) {
                    this.animateValue(priceEl, currentPrice, price, 300);
                }
            }
            if (buyBtn) buyBtn.disabled = false;
            if (sellBtn) sellBtn.disabled = false;

            const prevPrice = this.lastAnchorPrices[ticker];
            const targetPrice = this.anchorPrices[ticker] ?? price;
            if (prevPrice && prevPrice !== targetPrice) {
                const change = ((targetPrice - prevPrice) / prevPrice) * 100;
                if (changeEl) {
                    changeEl.textContent = `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`;
                    changeEl.className = `price-change ${change >= 0 ? 'positive' : 'negative'}`;
                }
                card.classList.toggle('price-rising', change > 0);
                card.classList.toggle('price-falling', change < 0);
            } else {
                if (changeEl) changeEl.textContent = '';
                card.classList.remove('price-rising', 'price-falling');
            }

            if (statusEl) {
                statusEl.textContent = '';
                statusEl.className = 'stock-status';
            }
        });
    }

    animateMarketTo(targetPrices, tickers = [], currentDate) {
        if (this.priceAnimationFrame) {
            cancelAnimationFrame(this.priceAnimationFrame);
        }

        const previousAnchorPrices = Object.keys(this.anchorPrices).length ? this.anchorPrices : this.currentPrices;
        this.lastAnchorPrices = { ...previousAnchorPrices };
        this.previousPrices = { ...previousAnchorPrices };
        this.anchorPrices = { ...targetPrices };
        tickers = tickers.length ? tickers : Object.keys(targetPrices);

        const startPrices = {};
        tickers.forEach(ticker => {
            const currentDisplay = this.displayPrices[ticker];
            const previous = this.currentPrices[ticker];
            const target = targetPrices[ticker];
            startPrices[ticker] = currentDisplay ?? previous ?? target;
        });

        const startedAt = performance.now();
        const step = (now) => {
            const progress = Math.min((now - startedAt) / this.priceAnimationDuration, 1);
            const interpolatedPrices = {};

            tickers.forEach(ticker => {
                const start = startPrices[ticker];
                const target = targetPrices[ticker];
                if (start === undefined || start === null || target === undefined || target === null) {
                    if (target !== undefined && target !== null) {
                        interpolatedPrices[ticker] = target;
                    }
                    return;
                }

                interpolatedPrices[ticker] = start + ((target - start) * progress);
            });

            this.displayPrices = interpolatedPrices;
            this.currentPrices = progress === 1 ? { ...targetPrices } : { ...interpolatedPrices };
            this.updatePrices(interpolatedPrices, tickers);
            this.updateCharts(currentDate, interpolatedPrices);
            this.updateLivePortfolioValues(interpolatedPrices);

            if (progress < 1) {
                this.priceAnimationFrame = requestAnimationFrame(step);
            } else {
                this.priceAnimationFrame = null;
                this.displayPrices = { ...targetPrices };
                this.currentPrices = { ...targetPrices };
            }
        };

        this.priceAnimationFrame = requestAnimationFrame(step);
    }

    updateCharts(currentDate, prices) {
        this.resetChartsOnDateJump(currentDate);
        const djiPrice = prices['^DJI'];
        const sp500Price = prices['^GSPC'];

        if (djiPrice !== undefined && djiPrice !== null) {
            this.addChartPoint(this.djiChart, this.djiLabels, this.djiData, currentDate, djiPrice);
            const djiValueEl = document.getElementById('dji-value');
            if (djiValueEl) djiValueEl.textContent = this.formatCurrency(djiPrice);
            this.updateChartMovement('chart-dji', '^DJI', djiPrice);
        }
        if (sp500Price !== undefined && sp500Price !== null && currentDate >= '1957-03-04') {
            this.addChartPoint(this.sp500Chart, this.sp500Labels, this.sp500Data, currentDate, sp500Price);
            const sp500ValueEl = document.getElementById('sp500-value');
            if (sp500ValueEl) sp500ValueEl.textContent = this.formatCurrency(sp500Price);
            this.updateChartMovement('chart-gspc', '^GSPC', sp500Price);
        }

        requestAnimationFrame(() => {
            try {
                if (this.djiChart && this.djiLabels.length > 0 && this.djiData.length > 0) {
                    this.djiChart.update('none');
                }
            } catch (e) {
                console.error('DJI chart update failed:', e, { labels: this.djiLabels, data: this.djiData });
            }
            try {
                if (this.sp500Chart && this.sp500Labels.length > 0 && this.sp500Data.length > 0) {
                    this.sp500Chart.update('none');
                }
            } catch (e) {
                console.error('SP500 chart update failed:', e, { labels: this.sp500Labels, data: this.sp500Data });
            }
        });
    }

    addChartPoint(chart, labels, data, date, value) {
        if (value === undefined || value === null) return;
        if (typeof value !== 'number' || !Number.isFinite(value)) {
            console.error('Invalid chart value:', { date, value, type: typeof value });
            return;
        }

        const lastLabel = labels[labels.length - 1];
        if (lastLabel === date) {
            data[data.length - 1] = value;
        } else {
            labels.push(date);
            data.push(value);
        }
        this.trimChartToPastTwentyYears(labels, data, date);

        if (labels.length !== data.length) {
            console.error('Labels and data array length mismatch:', { labelsLength: labels.length, dataLength: data.length, date, value });
            const minLen = Math.min(labels.length, data.length);
            labels.length = minLen;
            data.length = minLen;
        }

        if (chart) {
            chart.data.labels = labels;
            chart.data.datasets[0].data = this.smoothData(data);
        }
        console.log(`Chart point added: ${date}, value=${value}, labels.length=${labels.length}, data.length=${data.length}`);
    }

    trimChartToPastTwentyYears(labels, data, currentDate) {
        if (!currentDate || labels.length === 0) return;

        const current = new Date(currentDate);
        if (Number.isNaN(current.getTime())) return;

        const cutoff = new Date(current);
        cutoff.setFullYear(cutoff.getFullYear() - 20);

        let removed = 0;
        while (labels.length > 0) {
            const labelDate = new Date(labels[0]);
            if (Number.isNaN(labelDate.getTime())) {
                labels.shift();
                data.shift();
                removed++;
                continue;
            }
            if (labelDate >= cutoff) break;
            labels.shift();
            data.shift();
            removed++;
        }

        if (removed > 0) {
            console.log(`Trimmed ${removed} points before ${cutoff.toISOString().split('T')[0]}`);
        }
    }

    smoothData(data) {
        if (data.length < 5) return data;
        const smoothed = [];
        for (let i = 0; i < data.length; i++) {
            if (i === 0 || i === data.length - 1) {
                smoothed.push(data[i]);
            } else {
                const avg = (data[i - 1] + data[i] + data[i + 1]) / 3;
                smoothed.push(avg);
            }
        }
        return smoothed;
    }

    resetChartsOnDateJump(currentDate) {
        if (!currentDate || !this.djiLabels.length) return;

        const latestDate = new Date(currentDate);
        const lastChartDate = new Date(this.djiLabels[this.djiLabels.length - 1]);
        if (Number.isNaN(latestDate.getTime()) || Number.isNaN(lastChartDate.getTime())) return;

        const isBackward = latestDate < lastChartDate;

        console.log(`Date jump check: current=${currentDate}, lastChart=${this.djiLabels[this.djiLabels.length - 1]}, isBackward=${isBackward}`);

        if (isBackward) {
            console.warn(`Clearing charts due to backward date jump`);
            this.clearCharts();
        }
    }

    updateChartMovement(canvasId, ticker, price) {
        const wrapper = document.getElementById(canvasId)?.closest('.chart-wrapper');
        const prevPrice = this.previousPrices[ticker];
        if (!wrapper || !prevPrice || prevPrice === price) return;

        wrapper.classList.toggle('price-rising', price > prevPrice);
        wrapper.classList.toggle('price-falling', price < prevPrice);
    }

    clearCharts() {
        this.djiLabels.length = 0;
        this.djiData.length = 0;
        this.sp500Labels.length = 0;
        this.sp500Data.length = 0;
        if (this.djiChart) {
            this.djiChart.data.labels = [];
            this.djiChart.data.datasets[0].data = [];
            this.djiChart.update();
        }
        if (this.sp500Chart) {
            this.sp500Chart.data.labels = [];
            this.sp500Chart.data.datasets[0].data = [];
            this.sp500Chart.update();
        }
        const djiValueEl = document.getElementById('dji-value');
        const sp500ValueEl = document.getElementById('sp500-value');
        if (djiValueEl) djiValueEl.textContent = '--';
        if (sp500ValueEl) sp500ValueEl.textContent = '--';
    }

    updateModeUI() {
        const djiChartTitle = document.getElementById('dji-chart-title');
        if (djiChartTitle) djiChartTitle.textContent = 'Dow Jones Industrial Average (^DJI)';
        if (this.djiChart) {
            this.djiChart.data.datasets[0].label = 'Dow Jones';
            this.djiChart.update();
        }

        const sp500ChartWrapper = document.getElementById('sp500-chart-wrapper');
        if (sp500ChartWrapper) sp500ChartWrapper.style.display = '';
        const sp500ChartTitle = document.getElementById('sp500-chart-title');
        if (sp500ChartTitle) sp500ChartTitle.textContent = 'S&P 500 (^GSPC)';
        if (this.sp500Chart) {
            this.sp500Chart.data.datasets[0].label = 'S&P 500';
            this.sp500Chart.update();
        }

        document.querySelectorAll('.stock-card').forEach(card => {
            const ticker = card.dataset.ticker;
            card.style.display = ticker === '^DJI' || ticker === '^GSPC' ? '' : 'none';
        });
    }

    updateHeadlineTicker(data) {
        console.log('updateHeadlineTicker called:', data);
        const headlineEl = document.getElementById('headline-text');
        if (!headlineEl || !data) return;

        const dateString = data.current_date || data.date;
        const year = data.year || (dateString ? dateString.slice(0, 4) : null);

        if (data.headline && headlineEl) {
            headlineEl.textContent = data.headline;
        }
        const yearEl = document.getElementById('news-year-label');
        if (yearEl && year) {
            yearEl.textContent = `Year: ${year}`;
        }
    }

    handleMarketEvent(data) {
        if (!data) return;

        const eventType = data.type || 'generic';
        const message = data.message || 'Market event occurred';

        switch (eventType) {
            case 'reuben_born':
                this.showPopup('🎉 CELEBRATION', message, 'celebration');
                break;
            case 'sp500_launch':
                this.showPopup('📈 MARKET MILESTONE', message, 'milestone');
                break;
            case 'market_crash':
                this.showPopup('⚠️ MARKET CRASH', message, 'danger');
                break;
            default:
                this.showPopup('📰 MARKET EVENT', message, 'info');
        }
    }

    handleSECPenalty(data) {
        if (!data) return;
        this.showPopup('🚨 SEC ENFORCEMENT', data.message, 'danger');
        if (data.cash_remaining !== undefined) {
            const cashEl = document.getElementById('cash-balance');
            if (cashEl) cashEl.textContent = this.formatCurrency(data.cash_remaining);
        }
    }

    handleInsiderOpportunity(data) {
        if (!data) return;
        this.insiderOpportunityAvailable = data.available || false;

        const btn = document.getElementById('insider-rumor-btn');
        const statusEl = document.getElementById('insider-status');

        if (btn) {
            btn.disabled = !this.insiderOpportunityAvailable;
            btn.classList.toggle('available', this.insiderOpportunityAvailable);
        }
        if (statusEl) {
            statusEl.textContent = data.message || '';
            statusEl.classList.toggle('available', this.insiderOpportunityAvailable);
        }
    }

    handleInsiderRumor(data) {
        if (!data) return;
        this.showPopup('🕵️ INSIDER RUMOR', data.headline || data.message, 'insider');
    }

    handleInsiderTip(data) {
        if (!data) return;
        this.showPopup('💡 INSIDER TIP', `${data.tip}\n\n${data.message || ''}`, 'tip');
    }

    handleInsiderStatusUpdate(data) {
        if (!data) return;
        if (data.message) {
            this.showPopup('🔓 INSIDER STATUS', data.message, 'info');
        }
        const btn = document.getElementById('insider-rumor-btn');
        if (btn && data.is_insider !== undefined) {
            btn.classList.toggle('insider-active', data.is_insider);
        }
    }

    requestInsiderRumor() {
        if (!this.insiderOpportunityAvailable) {
            this.showPopup('🚫 No Insider Rumor', 'No insider opportunity is currently available.', 'warning');
            return;
        }
        const confirmed = confirm(
            '⚠️ INSIDER RUMOR WARNING\n\n' +
            'Viewing this rumor carries a 75% chance of an SEC audit.\n' +
            'If caught, you will lose 60% of your cash balance as a penalty.\n\n' +
            'Are you sure you want to proceed?'
        );
        if (!confirmed) return;
        this.socket.emit('request_insider_rumor');
    }

    handleGameOver(data) {
        if (!data) return;
        console.log('Game over:', data);

        const overlay = document.getElementById('game-over-overlay');
        const title = document.getElementById('game-over-title');
        const subtitle = document.getElementById('game-over-subtitle');
        const podium = document.getElementById('game-over-podium');

        if (title) title.textContent = `Game Over - ${data.current_date || 'Final Result'}`;
        if (subtitle) subtitle.textContent = `You ranked #${data.rank} out of ${data.total_players} players`;

        if (podium) {
            podium.innerHTML = (data.leaderboard || []).slice(0, 3).map(entry => `
                <div class="game-over-podium-row ${entry.username === window.username ? 'you' : ''}">
                    <span>#${entry.rank}</span>
                    <strong>${entry.username}${entry.username === window.username ? ' (You)' : ''}</strong>
                    <em>${this.formatCurrency(entry.net_worth)}</em>
                </div>
            `).join('');
        }

        if (overlay) overlay.classList.add('visible');
    }

    openTradeModal(ticker, type) {
        this.tradeTicker = ticker;
        this.tradeType = type;
        this.tradePrice = this.currentPrices[ticker] || 0;

        const modalTitle = document.getElementById('modal-title');
        const modalTicker = document.getElementById('modal-ticker');
        const modalPrice = document.getElementById('modal-price');
        const inputLabel = document.getElementById('trade-input-label');
        const inputField = document.getElementById('trade-amount');
        const totalLabel = document.getElementById('trade-total-label');

        if (modalTitle) modalTitle.textContent = type === 'buy' ? `Buy ${ticker}` : `Sell ${ticker}`;
        if (modalTicker) modalTicker.textContent = ticker;
        if (modalPrice) modalPrice.textContent = this.formatCurrency(this.tradePrice);

        if (inputLabel) inputLabel.textContent = 'Amount ($)';
        if (inputField) {
            inputField.placeholder = 'Dollar amount';
            inputField.value = '100';
        }
        if (totalLabel) totalLabel.textContent = type === 'buy' ? 'Shares to buy:' : 'Shares to sell:';

        this.updateTradeTotal();
        const modal = document.getElementById('trade-modal');
        if (modal) modal.classList.add('active');
    }

    closeModal() {
        const modal = document.getElementById('trade-modal');
        if (modal) modal.classList.remove('active');
    }

    updateTradeTotal() {
        const input = document.getElementById('trade-amount');
        const totalEl = document.getElementById('trade-total');
        if (!input || !totalEl) return;

        const dollarAmount = parseFloat(input.value) || 0;
        const shares = dollarAmount / this.tradePrice;
        totalEl.textContent = shares.toFixed(4) + ' shares';
    }

    executeTrade() {
        const input = document.getElementById('trade-amount');
        if (!input) return;

        const dollarAmount = parseFloat(input.value);
        if (!this.tradeTicker || !dollarAmount || dollarAmount <= 0) {
            console.error('Invalid trade data');
            return;
        }

        const tradeData = { ticker: this.tradeTicker };

        if (this.tradeType === 'buy') {
            tradeData.amount = dollarAmount;
        } else {
            const shares = dollarAmount / this.tradePrice;
            const currentShares = this.holdings[this.tradeTicker] || 0;

            if (shares > currentShares) {
                alert(`You only have ${currentShares.toFixed(4)} shares of ${this.tradeTicker}. You cannot sell $${dollarAmount.toFixed(2)} worth.`);
                return;
            }

            tradeData.shares = shares;
        }

        this.socket.emit(this.tradeType === 'buy' ? 'execute_buy' : 'execute_sell', tradeData);
        this.closeModal();
    }

    updateLeaderboard(entries) {
        console.log('updateLeaderboard called:', entries);
        const list = document.getElementById('leaderboard-list');
        if (!list) return;

        list.innerHTML = entries.map((entry, index) => {
            const rank = entry.rank || index + 1;
            const rankClass = rank === 1 ? 'gold' : rank === 2 ? 'silver' : rank === 3 ? 'bronze' : 'other';
            const medal = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : rank;
            const isCurrentUser = entry.username === window.username;
            const total = entries.length;
            const subtitle = (() => {
                if (rank === 1) return 'Wolf of Wall Street';
                if (rank === 2) return 'So close, yet so far';
                if (rank === 3) return 'Bronze medalist';
                if (rank === total) return 'Red Lantern — Bagholder Supreme';
                if (rank === total - 1) return 'Falling Knife';
                if (rank >= total - 2) return 'Paper Hands';
                if (rank <= Math.ceil(total * 0.25)) return 'Top quartile';
                if (rank >= Math.floor(total * 0.75)) return 'Bottom quartile';
                return 'Average Joe';
            })();
            return `
            <div class="leaderboard-item ${isCurrentUser ? 'current-user' : ''}">
                <span class="leaderboard-rank ${rankClass}">${medal}</span>
                <div class="leaderboard-info">
                    <span class="leaderboard-name ${isCurrentUser ? 'you' : ''}">${entry.username}${isCurrentUser ? ' (You)' : ''}</span>
                    <span class="leaderboard-subtitle">${subtitle}</span>
                </div>
                <span class="leaderboard-worth">${this.formatCurrency(entry.net_worth)}</span>
            </div>
            `;
        }).join('');
    }

    updatePortfolio(data) {
        console.log('updatePortfolio called:', data);
        this.cash = Number(data.cash || 0);
        this.holdings = data.holdings || {};

        const cashEl = document.getElementById('cash-balance');
        if (cashEl) cashEl.textContent = this.formatCurrency(data.cash);

        this.updateLivePortfolioValues(this.currentPrices);

        const holdingsList = document.getElementById('holdings-list');
        if (!holdingsList) return;

        if (Object.keys(this.holdings).length === 0) {
            holdingsList.innerHTML = '<p class="empty-message">No holdings yet</p>';
        } else {
            holdingsList.innerHTML = Object.entries(this.holdings).map(([ticker, shares]) => `
                <div class="holding-item">
                    <span class="holding-ticker">${ticker}</span>
                    <span class="holding-shares">${Number(shares).toFixed(2)} shares</span>
                    <span class="holding-value">${this.formatCurrency((this.currentPrices[ticker] || 0) * Number(shares))}</span>
                </div>
            `).join('');
        }
    }

    updateLivePortfolioValues(prices) {
        const netWorthEl = document.getElementById('net-worth');
        const holdingsValueEl = document.getElementById('holdings-value');

        let holdingsValue = 0;
        for (const [ticker, shares] of Object.entries(this.holdings)) {
            const price = prices[ticker] || this.currentPrices[ticker] || 0;
            holdingsValue += price * Number(shares);
        }

        const netWorth = this.cash + holdingsValue;

        if (netWorthEl) netWorthEl.textContent = this.formatCurrency(netWorth);
        if (holdingsValueEl) holdingsValueEl.textContent = this.formatCurrency(holdingsValue);
    }

    animateValue(element, start, end, duration) {
        if (!element) return;
        const startTime = performance.now();
        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const current = start + (end - start) * progress;
            element.textContent = this.formatCurrency(current);
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };
        requestAnimationFrame(animate);
    }

    showPopup(title, message, type = 'info') {
        const container = document.getElementById('popup-container');
        if (!container) return;

        const popup = document.createElement('div');
        popup.className = `popup popup-${type}`;
        popup.innerHTML = `
            <div class="popup-header">
                <span class="popup-title">${title}</span>
                <button class="popup-close">&times;</button>
            </div>
            <div class="popup-body">${message.replace(/\n/g, '<br>')}</div>
        `;

        popup.querySelector('.popup-close').addEventListener('click', () => popup.remove());
        container.appendChild(popup);

        setTimeout(() => popup.remove(), 8000);
    }

    formatCurrency(value) {
        if (value === undefined || value === null || Number.isNaN(value)) return '$0.00';
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(value);
    }

    checkSP500Availability(currentDate) {
        if (!currentDate) return;

        const sp500IPODate = '1957-03-04';
        const chartsRow = document.getElementById('charts-row');
        const djiColumn = document.getElementById('dji-column');
        const sp500Column = document.getElementById('sp500-column');
        const sp500Placeholder = document.getElementById('sp500-placeholder');
        const buyBtn = document.getElementById('btn-buy-^GSPC');
        const sellBtn = document.getElementById('btn-sell-^GSPC');
        const statusEl = document.getElementById('status-^GSPC');

        if (currentDate < sp500IPODate) {
            if (chartsRow) chartsRow.classList.add('full-width');
            if (djiColumn) djiColumn.style.width = '100%';
            if (sp500Column) sp500Column.style.display = 'none';
            if (sp500Placeholder) sp500Placeholder.style.display = 'flex';
            if (buyBtn) buyBtn.disabled = true;
            if (sellBtn) sellBtn.disabled = true;
            if (statusEl) {
                statusEl.textContent = 'Not yet IPO\'d';
                statusEl.className = 'stock-status unavailable';
            }
        } else {
            if (chartsRow) chartsRow.classList.remove('full-width');
            if (djiColumn) djiColumn.style.width = '50%';
            if (sp500Column) sp500Column.style.width = '50%';
            if (sp500Placeholder) sp500Placeholder.style.display = 'none';
            if (sp500Column) sp500Column.style.display = 'flex';
            if (buyBtn) buyBtn.disabled = false;
            if (sellBtn) sellBtn.disabled = false;
        }
    }

    handleDateDrivenEvents(currentDate) {
        if (!currentDate) return;
        this.checkSP500Availability(currentDate);

        if (currentDate < '1980-01-01') {
            this.reubenCelebrated = false;
        }

        if (!this.reubenCelebrated && currentDate >= '1980-01-01') {
            this.reubenCelebrated = true;
        }
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.stockSimulator = new StockSimulator();
});
