/* js/main.js */
const searchBtn = document.getElementById('searchBtn');
const usernameInput = document.getElementById('usernameInput');

const loader = document.getElementById('loader');
const errorBox = document.getElementById('errorBox');
const dashboard = document.getElementById('dashboard');

// Store chart instances for cleanup
let chartInstances = [];

function handleEnter(e) {
    if (e.key === 'Enter') {
        fetchStats();
    }
}

function setAndFetch(name) {
    usernameInput.value = name;
    fetchStats();
}

// Initialize Supabase Client
// Note: Em produção, estas chaves podem ser públicas (anon key), o RLS protege os dados.
const SUPABASE_URL = 'VAI_MUDAR_NA_HOSPEDAGEM_AQUI_COLOCAR_A_Sua';
const SUPABASE_ANON_KEY = 'VAI_MUDAR_NA_HOSPEDAGEM_AQUI_COLOCAR_A_Sua';

const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// Auth Elements
const authModal = document.getElementById('authModal');
const authEmail = document.getElementById('authEmail');
const authBtn = document.getElementById('authBtn');
const authMessage = document.getElementById('authMessage');
const logoutBtn = document.getElementById('logoutBtn');

let sessionUser = null;

// Auth Logic
async function checkAuth() {
    const { data } = await supabase.auth.getSession();
    if (data.session) {
        sessionUser = data.session.user;
        authModal.classList.add('hidden');
        logoutBtn.classList.remove('hidden');
    } else {
        sessionUser = null;
        authModal.classList.remove('hidden');
        logoutBtn.classList.add('hidden');
        dashboard.classList.add('hidden');
    }
}

supabase.auth.onAuthStateChange((event, session) => {
    if (event === 'SIGNED_IN' || event === 'SIGNED_OUT') {
        checkAuth();
    }
});

authBtn.addEventListener('click', async () => {
    const email = authEmail.value.trim();
    if (!email) return;

    authBtn.disabled = true;
    authMessage.innerText = 'Enviando link mágico...';
    authMessage.className = 'auth-message';

    const { error } = await supabase.auth.signInWithOtp({
        email: email,
        options: {
            // Em produção configurar a URL de redirecionamento no painel
            emailRedirectTo: window.location.origin
        }
    });

    if (error) {
        authMessage.innerText = 'Erro: ' + error.message;
        authMessage.className = 'auth-message auth-error';
    } else {
        authMessage.innerText = 'Link enviado! Verifique seu email.';
        authMessage.className = 'auth-message auth-success';
    }
    authBtn.disabled = false;
});

logoutBtn.addEventListener('click', async () => {
    await supabase.auth.signOut();
});

// Check auth on load
checkAuth();

async function fetchStats() {
    if (!sessionUser) {
        errorBox.classList.remove('hidden');
        document.getElementById('errorMessage').innerText = "Faça login para buscar stats.";
        return;
    }

    const username = usernameInput.value.trim();
    if (!username) return;

    // UI States
    dashboard.classList.add('hidden');
    errorBox.classList.add('hidden');
    loader.classList.remove('hidden');

    const statusText = document.getElementById('loaderStatus');
    statusText.innerText = `Buscando dados de ${username} no Supabase...`;

    try {
        // 1. Fetch Player
        const { data: player, error: playerError } = await supabase
            .from('players')
            .select('id, username')
            .ilike('username', username)
            .single();

        if (playerError || !player) {
            throw new Error('Jogador não encontrado no banco de dados.');
        }

        // 2. Fetch Latest Snapshot
        const { data: snapshot, error: snapError } = await supabase
            .from('snapshots')
            .select('id, status, scraped_at')
            .eq('player_id', player.id)
            .order('scraped_at', { ascending: false })
            .limit(1)
            .single();

        if (snapError || !snapshot) throw new Error('Nenhum dado raspado para este jogador.');
        if (snapshot.status !== 'sucesso') throw new Error(`Último scraping falhou: ${snapshot.status}`);

        // 3. Fetch All Associated Data concurrently
        const snapshotId = snapshot.id;

        const [
            { data: overview },
            { data: periodStats },
            { data: modeStats },
            { data: rankInfo },
            { data: recentMatches }
        ] = await Promise.all([
            supabase.from('overview_stats').select('*').eq('snapshot_id', snapshotId).single(),
            supabase.from('period_stats').select('*').eq('snapshot_id', snapshotId),
            supabase.from('mode_stats').select('*').eq('snapshot_id', snapshotId),
            supabase.from('rank_info').select('*').eq('snapshot_id', snapshotId),
            supabase.from('recent_matches').select('*').eq('snapshot_id', snapshotId)
        ]);

        // Reconstruct the nested object structure expected by renderDashboard
        const reconstructedPlayer = {
            nome_usuario: player.username,
            overview: {
                tempo_de_jogo: overview?.play_time || 'N/A',
                nivel_passe_de_batalha: overview?.battle_pass_level || 'N/A'
            },
            estatisticas_gerais: {
                vitorias: overview?.wins || 0,
                kd_ratio: overview?.kd_ratio || 0.0,
                porcentagem_vitoria: overview?.win_percentage || '0%',
                total_kills: overview?.total_kills || 0,
                partidas_jogadas: overview?.total_matches || 0
            },
            estatisticas_periodo: (periodStats || []).map(ps => ({
                periodo: ps.period_name,
                partidas: ps.matches,
                vitorias: ps.wins,
                porcentagem_vitoria: ps.win_percentage,
                kd_ratio: ps.kd_ratio,
                kills: ps.kills
            })),
            estatisticas_por_modo: (modeStats || []).map(ms => ({
                modo: ms.mode_name,
                partidas: ms.matches,
                tracker_rating: ms.tracker_rating,
                vitorias: ms.wins,
                porcentagem_vitoria: ms.win_percentage,
                kills: ms.kills,
                kd_ratio: ms.kd_ratio
            })),
            ranks: (rankInfo || []).map(ri => ({
                modo: ri.mode_name,
                rank_atual: ri.current_rank,
                melhor_rank: ri.best_rank
            })),
            partidas_recentes: (recentMatches || []).map(rm => ({
                data: rm.session_header,
                detalhes: rm.match_details || []
            }))
        };

        renderDashboard(reconstructedPlayer);

        loader.classList.add('hidden');
        dashboard.classList.remove('hidden');

    } catch (err) {
        loader.classList.add('hidden');
        document.getElementById('errorMessage').innerText = err.message;
        errorBox.classList.remove('hidden');
    }
}

// ── Color palette for modes ──────────────────────────────────────
const MODE_COLORS = {
    'SOLO': { bg: 'rgba(0, 210, 255, 0.15)', border: '#00d2ff', chart: 'rgba(0, 210, 255, 0.6)' },
    'DUOS': { bg: 'rgba(157, 78, 221, 0.15)', border: '#9d4edd', chart: 'rgba(157, 78, 221, 0.6)' },
    'TRIOS': { bg: 'rgba(255, 107, 107, 0.15)', border: '#ff6b6b', chart: 'rgba(255, 107, 107, 0.6)' },
    'SQUADS': { bg: 'rgba(255, 215, 0, 0.15)', border: '#ffd700', chart: 'rgba(255, 215, 0, 0.6)' },
    'LTM': { bg: 'rgba(38, 222, 129, 0.15)', border: '#26de81', chart: 'rgba(38, 222, 129, 0.6)' },
};

function getModeColor(modo) {
    return MODE_COLORS[modo] || { bg: 'rgba(255,255,255,0.1)', border: '#ffffff', chart: 'rgba(255,255,255,0.5)' };
}

// ── Rank name translation ────────────────────────────────────────
function translateRankMode(modo) {
    const map = {
        'Battle Royale (Build)': 'BR Construção',
        'Battle Royale (Zero Build)': 'BR Zero Construção',
        'Reload (Build)': 'Carga Dupla',
        'Reload (Zero Build)': 'Carga Dupla (Zero)',
        'Rocket Racing': 'Corrida (Rocket)',
    };
    return map[modo] || modo;
}

function renderDashboard(player) {
    // Destroy previous charts
    chartInstances.forEach(c => c.destroy());
    chartInstances = [];

    // ── 1. Header ───────────────────────────────────────────────
    document.getElementById('playerName').innerText = player.nome_usuario;
    document.getElementById('playTime').innerHTML = `<i class="far fa-clock"></i> ${player.overview.tempo_de_jogo}`;
    document.getElementById('bpLevel').innerHTML = `<i class="fas fa-star"></i> BP ${player.overview.nivel_passe_de_batalha}`;

    // Lifetime Footer
    document.getElementById('ltWins').innerText = player.estatisticas_gerais.vitorias;
    document.getElementById('ltKills').innerText = player.estatisticas_gerais.total_kills;

    // ── 2. Ranks (Dinâmicos) ────────────────────────────────────
    const ranksGrid = document.getElementById('ranksGrid');
    ranksGrid.innerHTML = '';

    if (player.ranks && player.ranks.length > 0) {
        player.ranks.forEach(rank => {
            const card = document.createElement('div');
            card.className = 'rank-card glass-card';
            card.innerHTML = `
                <span class="rank-title">${translateRankMode(rank.modo)}</span>
                <strong class="rank-value">${rank.rank_atual}</strong>
                <span class="rank-peak">Melhor: ${rank.melhor_rank}</span>
            `;
            ranksGrid.appendChild(card);
        });
    }

    // ── 3. Period Stats ─────────────────────────────────────────
    const p7 = player.estatisticas_periodo.find(p => p.periodo === 'Last 7 Days');
    const p30 = player.estatisticas_periodo.find(p => p.periodo === 'Last 30 Days');

    if (p7) {
        document.getElementById('p7Matches').innerText = p7.partidas;
        document.getElementById('p7Wins').innerText = `${p7.vitorias} (${p7.porcentagem_vitoria})`;
        document.getElementById('p7KD').innerText = p7.kd_ratio;
        document.getElementById('p7Kills').innerText = p7.kills;
    }
    if (p30) {
        document.getElementById('p30Matches').innerText = p30.partidas;
        document.getElementById('p30Wins').innerText = `${p30.vitorias} (${p30.porcentagem_vitoria})`;
        document.getElementById('p30KD').innerText = p30.kd_ratio;
        document.getElementById('p30Kills').innerText = p30.kills;
    }

    // ── 4. Modos (Todos - Dinâmicos) ────────────────────────────
    const modesGrid = document.getElementById('modesGrid');
    modesGrid.innerHTML = '';

    if (player.estatisticas_por_modo && player.estatisticas_por_modo.length > 0) {
        player.estatisticas_por_modo.forEach(modo => {
            const colors = getModeColor(modo.modo);
            const card = document.createElement('div');
            card.className = 'mode-card glass-card';
            card.style.borderTop = `2px solid ${colors.border}`;
            card.innerHTML = `
                <div class="mode-header">
                    <h3>${modo.modo}</h3>
                    <span class="tracker-rating">TR: ${modo.tracker_rating}</span>
                </div>
                <div class="mode-stats">
                    <div class="sm-stat"><span>Partidas</span><strong>${modo.partidas}</strong></div>
                    <div class="sm-stat"><span>Vitórias</span><strong style="color:${colors.border}">${modo.vitorias} (${modo.porcentagem_vitoria})</strong></div>
                    <div class="sm-stat"><span>Abates/Mortes</span><strong>${modo.kd_ratio}</strong></div>
                    <div class="sm-stat"><span>Abates</span><strong>${modo.kills}</strong></div>
                </div>
            `;
            modesGrid.appendChild(card);
        });
    }

    // ── 5. Gráficos Individuais (Radar) ─────────────────────────
    renderIndividualCharts(player.estatisticas_por_modo);

    // ── 6. Gráfico Comparativo (Bar) ────────────────────────────
    renderCompareChart(player.estatisticas_por_modo);

    // ── 7. Sessões Recentes ─────────────────────────────────────
    const matchesContainer = document.getElementById('matchesContainer');
    matchesContainer.innerHTML = '';

    if (player.partidas_recentes && player.partidas_recentes.length > 0) {
        const recentSessions = player.partidas_recentes.slice(0, 3);

        recentSessions.forEach(session => {
            session.detalhes.forEach(match => {
                const isWin = match.resultado && (match.resultado.includes('1st') || match.resultado.includes('Win'));

                const html = `
                <div class="match-item ${isWin ? 'win' : ''}">
                    <div class="match-head">
                        <span class="match-res">${match.resultado || '-'}</span>
                        <span class="match-tr">${match.tracker_rating ? match.tracker_rating.replace('Tracker Rating\n', '') : ''}</span>
                    </div>
                    <div class="match-desc">${match.descricao || ''}</div>
                    <div class="match-bottom">
                        <div class="m-stat">Abates <strong>${match.Kills || 0}</strong></div>
                        <div class="m-stat">Pontuação <strong>${match.Score || 0}</strong></div>
                    </div>
                </div>
                `;
                matchesContainer.innerHTML += html;
            });
        });
    } else {
        matchesContainer.innerHTML = '<p style="color:var(--text-muted);font-size:12px;text-align:center;">Nenhuma partida recente.</p>';
    }
}

// ══════════════════════════════════════════════════════════════════
// CHARTS
// ══════════════════════════════════════════════════════════════════

function renderIndividualCharts(modos) {
    const grid = document.getElementById('individualChartsGrid');
    grid.innerHTML = '';

    if (!modos || modos.length === 0) return;

    // Compute max values for normalization across all modes
    const maxKills = Math.max(...modos.map(m => m.kills), 1);
    const maxWins = Math.max(...modos.map(m => m.vitorias), 1);
    const maxMatches = Math.max(...modos.map(m => m.partidas), 1);

    modos.forEach(modo => {
        const colors = getModeColor(modo.modo);

        const card = document.createElement('div');
        card.className = 'chart-card';
        card.innerHTML = `
            <h4>${modo.modo}</h4>
            <div class="chart-container"><canvas></canvas></div>
            <div class="chart-stats-summary">
                <div class="chart-stat"><span>Vitórias</span><strong>${modo.vitorias}</strong></div>
                <div class="chart-stat"><span>% Vitória</span><strong>${modo.porcentagem_vitoria}</strong></div>
                <div class="chart-stat"><span>Abates/Mortes</span><strong>${modo.kd_ratio}</strong></div>
                <div class="chart-stat"><span>Abates</span><strong>${modo.kills}</strong></div>
                <div class="chart-stat"><span>Partidas</span><strong>${modo.partidas}</strong></div>
            </div>
        `;
        grid.appendChild(card);

        const canvas = card.querySelector('canvas');
        const ctx = canvas.getContext('2d');

        const winPctNum = parseFloat(modo.porcentagem_vitoria) || 0;

        const chart = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: ['Vitórias', '% Vitória', 'Abates/Mortes', 'Abates', 'Partidas'],
                datasets: [{
                    label: modo.modo,
                    data: [
                        (modo.vitorias / maxWins) * 100,
                        winPctNum,
                        Math.min(modo.kd_ratio * 20, 100),   // Scale K/D
                        (modo.kills / maxKills) * 100,
                        (modo.partidas / maxMatches) * 100,
                    ],
                    backgroundColor: colors.bg,
                    borderColor: colors.border,
                    borderWidth: 2,
                    pointBackgroundColor: colors.border,
                    pointBorderColor: '#fff',
                    pointRadius: 3,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) {
                                const idx = ctx.dataIndex;
                                const raw = [modo.vitorias, modo.porcentagem_vitoria, modo.kd_ratio, modo.kills, modo.partidas];
                                const labels = ['Vitórias', '% Vitória', 'A/M', 'Abates', 'Partidas'];
                                return `${labels[idx]}: ${raw[idx]}`;
                            }
                        }
                    }
                },
                scales: {
                    r: {
                        angleLines: { color: 'rgba(255,255,255,0.05)' },
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        pointLabels: {
                            color: '#8e8e9f',
                            font: { size: 10, family: 'Outfit' },
                        },
                        ticks: { display: false },
                        suggestedMin: 0,
                        suggestedMax: 100,
                    }
                }
            }
        });
        chartInstances.push(chart);
    });
}

function renderCompareChart(modos) {
    const canvas = document.getElementById('compareChart');
    if (!canvas || !modos || modos.length === 0) return;

    const ctx = canvas.getContext('2d');

    const labels = modos.map(m => m.modo);
    const borderColors = modos.map(m => getModeColor(m.modo).border);
    const bgColors = modos.map(m => getModeColor(m.modo).chart);

    const chart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Vitórias',
                    data: modos.map(m => m.vitorias),
                    backgroundColor: bgColors.map(c => c.replace('0.6', '0.7')),
                    borderColor: borderColors,
                    borderWidth: 1,
                    borderRadius: 4,
                },
                {
                    label: 'Abates/Mortes (K/D × 100)',
                    data: modos.map(m => Math.round(m.kd_ratio * 100)),
                    backgroundColor: bgColors.map(c => c.replace('0.6', '0.4')),
                    borderColor: borderColors,
                    borderWidth: 1,
                    borderRadius: 4,
                },
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    labels: {
                        color: '#8e8e9f',
                        font: { family: 'Outfit', size: 12 },
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function (ctx) {
                            if (ctx.datasetIndex === 1) {
                                return `K/D: ${(ctx.raw / 100).toFixed(2)}`;
                            }
                            return `Vitórias: ${ctx.raw}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#8e8e9f', font: { family: 'Outfit' } },
                    grid: { color: 'rgba(255,255,255,0.03)' },
                },
                y: {
                    ticks: { color: '#8e8e9f', font: { family: 'Outfit' } },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                }
            }
        }
    });
    chartInstances.push(chart);
}
