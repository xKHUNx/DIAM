document.addEventListener('DOMContentLoaded', function () {
    // DOM elements
    const fileInput = document.getElementById('jsonFile');
    const loadBtn = document.getElementById('loadBtn');
    const resetBtn = document.getElementById('resetBtn');
    const summaryBtn = document.getElementById('summaryBtn');
    const edgeStyleBtn = document.getElementById('edgeStyleBtn');
    const conversationSelect = document.getElementById('conversationSelect');
    const summaryModal = document.getElementById('summaryModal');
    const closeBtn = summaryModal.querySelector('.close');
    const speakersList = document.getElementById('speakers-list');
    const relationsList = document.getElementById('relations-list');
    const eduText = document.getElementById('edu-text');
    const eduSpeaker = document.getElementById('edu-speaker');
    const eduAddressees = document.getElementById('edu-addressees');
    const relationType = document.getElementById('relation-type');
    const relationSource = document.getElementById('relation-source');
    const relationTarget = document.getElementById('relation-target');
    const totalRelations = document.getElementById('total-relations');
    const totalNodes = document.getElementById('total-nodes');
    const backEdgesCount = document.getElementById('back-edges-count');
    const backEdgesList = document.getElementById('back-edges-list');
    const orphanedNodesCount = document.getElementById('orphaned-nodes-count');
    const orphanedNodesList = document.getElementById('orphaned-nodes-list');
    const orphanedClustersCount = document.getElementById('orphaned-clusters-count');
    const orphanedClustersList = document.getElementById('orphaned-clusters-list');
    const relationCountsList = document.getElementById('relation-counts-list');

    // Add search panel elements
    const searchPanel = document.createElement('div');
    searchPanel.id = 'search-panel';
    searchPanel.className = 'search-panel';
    searchPanel.innerHTML = `
        <input type="text" id="search-input" placeholder="Search for text or node ID...">
        <button id="search-btn">Search</button>
        <button id="clear-search-btn">Clear</button>
    `;
    const vizContainer = document.querySelector('.visualization-container');
    vizContainer.parentNode.insertBefore(searchPanel, vizContainer);

    const searchInput = document.getElementById('search-input');
    const searchBtn = document.getElementById('search-btn');
    const clearSearchBtn = document.getElementById('clear-search-btn');

    // State objects
    const speakerColors = {};  // Will store speaker -> color mappings
    let loadedData = null; // Store the full loaded JSON data (array or object)
    let currentConversationIndex = 0;

    // Edge style state
    let useCurvedEdges = true;

    // Edge style configurations
    const edgeStyles = {
        curved: {
            'curve-style': 'unbundled-bezier',
            'control-point-distances': function (ele) {
                let parallelEdges = ele.parallelEdges(); // Get all edges between the same nodes
                let index = parallelEdges.indexOf(ele); // Get unique index among them

                if (index === 0) return 50;  // First edge: Strong curve right
                if (index === 1) return -50; // Second edge: Strong curve left
                if (index === 2) return 0;   // Third edge: Straight

                // Alternating pattern for the rest
                let baseOffset = 50; // Base distance for separation
                let factor = (index - 1) / 2 + 1; // Gradual reduction after the first two
                let sign = index % 2 === 0 ? 1 : -1; // Alternate direction

                return sign * (baseOffset / factor); // Reduce curvature for later edges
            },
            'control-point-weights': function (ele) {
                let index = ele.parallelEdges().indexOf(ele);
                return index < 2 ? 0.5 : 0.4; // First two edges keep strong curve, others slightly adjusted
            },
            'edge-distances': 'node-position',
            'target-arrow-shape': 'triangle'
        },
        straight: {
            'curve-style': 'straight',
            'edge-distances': 'node-position'
        }
    };


    // Toggle edge style function
    function toggleEdgeStyle() {
        useCurvedEdges = !useCurvedEdges;
        const style = useCurvedEdges ? edgeStyles.curved : edgeStyles.straight;

        cy.style()
            .selector('edge')
            .style(style)
            .update();

        edgeStyleBtn.textContent = useCurvedEdges ? 'Use Straight Edges' : 'Use Curved Edges';
    }

    // Add edge style toggle button listener
    edgeStyleBtn.addEventListener('click', toggleEdgeStyle);

    // Modal event listeners
    summaryBtn.addEventListener('click', function () {
        updateSummaryStats();
        summaryModal.style.display = 'block';
    });

    closeBtn.addEventListener('click', function () {
        summaryModal.style.display = 'none';
    });

    window.addEventListener('click', function (event) {
        if (event.target === summaryModal) {
            summaryModal.style.display = 'none';
        }
    });

    // Search functionality
    function performSearch() {
        const searchTerm = searchInput.value.toLowerCase();
        if (!searchTerm) return;

        // Reset all nodes and edges to default state
        cy.elements().removeClass('search-highlight');
        cy.elements().style('opacity', 1);

        // Find matching nodes
        const matchingNodes = cy.nodes().filter(node => {
            const nodeId = node.id().toLowerCase();
            const nodeText = node.data('eduText').toLowerCase();
            return nodeId.includes(searchTerm) || nodeText.includes(searchTerm);
        });

        if (matchingNodes.length > 0) {
            // Highlight matching nodes
            matchingNodes.addClass('search-highlight');

            // Dim non-matching elements
            cy.elements().not(matchingNodes).style('opacity', 0.2);

            // Center the view on matching nodes
            cy.center(matchingNodes, 50);
        }
    }

    // Clear search results
    function clearSearch() {
        searchInput.value = '';
        cy.elements().removeClass('search-highlight');
        cy.elements().style('opacity', 1);
        // Removed the cy.fit() call to maintain current view
    }

    // Event listeners for search
    searchBtn.addEventListener('click', performSearch);
    searchInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter') performSearch();
    });
    clearSearchBtn.addEventListener('click', clearSearch);

    // Initialize cytoscape instance
    let cy = cytoscape({
        container: document.getElementById('cy'),
        style: [
            {
                selector: '.search-highlight',
                style: {
                    'border-width': 3,
                    'border-color': '#ff0',
                    'border-style': 'solid',
                    'background-color': 'data(color)',
                    'opacity': 1,
                    'z-index': 999
                }
            },
            {
                selector: 'node',
                style: {
                    'background-color': 'data(color)',
                    'label': 'data(id)',
                    'color': '#fff',
                    'text-outline-color': '#000',
                    'text-outline-width': 1,
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'width': 'data(nodeSize)',
                    'height': 'data(nodeSize)',
                    'shape': 'data(shape)',
                    'background-opacity': 'data(opacity)'
                }
            },
            {
                selector: '.search-highlight',
                style: {
                    'border-width': 3,
                    'border-color': '#ff0',
                    'border-style': 'solid',
                    'background-color': 'data(color)',
                    'opacity': 1,
                    'z-index': 999
                }
            },
            {
                selector: 'node:selected',
                style: {
                    'border-width': 3,
                    'border-color': '#000',
                    'border-style': 'solid'
                }
            },
            {
                selector: '.search-highlight',
                style: {
                    'border-width': 3,
                    'border-color': '#ff0',
                    'border-style': 'solid',
                    'background-color': 'data(color)',
                    'opacity': 1,
                    'z-index': 999
                }
            },
            {
                selector: 'edge',
                style: {
                    'width': 3,
                    'line-color': 'data(color)',
                    'target-arrow-color': 'data(color)',
                    'target-arrow-shape': 'triangle',
                    ...edgeStyles.curved
                }
            },
            {
                selector: '.search-highlight',
                style: {
                    'border-width': 3,
                    'border-color': '#ff0',
                    'border-style': 'solid',
                    'background-color': 'data(color)',
                    'opacity': 1,
                    'z-index': 999
                }
            },
            {
                selector: 'edge:selected',
                style: {
                    'width': 5,
                    'line-color': 'data(color)',
                    'target-arrow-color': 'data(color)',
                    'shadow-blur': 10,
                    'shadow-color': '#000',
                    'shadow-opacity': 0.5
                }
            }
        ],
        layout: {
            name: 'grid',
            rows: 3
        },
        selectionType: 'single' // Only allow one element to be selected at a time
    });

    // Color mapping
    const relationColors = {
        'Acknowledgment': '#800000',      // Maroon
        'Alternation': '#B22222',        // Bright Red
        'Background': '#FF4500',        // Darker Orange
        'Clarification_question': '#FF8C00', // Lighter Orange
        'Contrast': '#9ACD32',          // Yellow-Green
        'Correction': '#228B22',        // Green
        'Comment': '#006400',           // Dark Green
        'Conditional': '#40E0D0',       // Turquoise
        'Continuation': '#2196F3',      // Light Blue
        'Elaboration': '#0000CD',       // Royal Blue
        'Explanation': '#00008B',       // Dark Blue
        'Interruption': '#4B0082',      // Indigo
        'Narration': '#800080',         // Purple
        'Parallel': '#DA70D6',          // Orchid Pink
        'Q-Elab': '#A9A9A9',            // Dark Gray
        'Question-answer_pair': '#000000', // Black
        'Result': '#8B4513',            // Saddle Brown
        'default': '#999999'            // Gray
    };

    // Generate a color from a string
    function stringToColor(str) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            hash = str.charCodeAt(i) + ((hash << 5) - hash);
        }
        let color = '#';
        for (let i = 0; i < 3; i++) {
            const value = (hash >> (i * 8)) & 0xFF;
            color += ('00' + value.toString(16)).substr(-2);
        }
        return color;
    }

    // Load and process the JSON file
    // Load and process the JSON file
    loadBtn.addEventListener('click', function () {
        const file = fileInput.files[0];
        if (!file) {
            alert('Please select a JSON file first.');
            return;
        }

        const reader = new FileReader();
        reader.onload = function (e) {
            try {
                loadedData = JSON.parse(e.target.result);

                // Check format
                if (Array.isArray(loadedData)) {
                    // Populate dropdown
                    populateConversationSelect(loadedData);
                    conversationSelect.style.display = 'inline-block';
                    // Load first one
                    loadConversation(0);
                } else {
                    // Single object
                    conversationSelect.style.display = 'none';
                    processConversationData(loadedData);
                }
            } catch (error) {
                alert('Error parsing JSON file: ' + error.message);
            }
        };
        reader.readAsText(file);
    });

    function populateConversationSelect(data) {
        conversationSelect.innerHTML = '';
        data.forEach((item, index) => {
            const option = document.createElement('option');
            option.value = index;
            // Try to find a meaningful label, e.g. first EDU text or ID
            let label = `Conversation ${index + 1}`;
            const firstEdu = item.edus && item.edus.length > 0 ? item.edus[0] : null;
            if (item.id) {
                label += ` (${item.id})`;
            } else if (firstEdu) {
                label += `: ${firstEdu.text.substring(0, 30)}...`;
            }
            option.textContent = label;
            conversationSelect.appendChild(option);
        });

        // Listener for change
        conversationSelect.onchange = function () {
            loadConversation(parseInt(this.value));
        };
    }

    function loadConversation(index) {
        if (!loadedData || !loadedData[index]) return;
        currentConversationIndex = index;
        processConversationData(loadedData[index]);
    }

    // Reset the visualization
    resetBtn.addEventListener('click', function () {
        cy.elements().remove();
        speakersList.innerHTML = '';
        relationsList.innerHTML = '';
        clearInfoPanels();
        fileInput.value = '';
        loadedData = null;
        conversationSelect.style.display = 'none';
        conversationSelect.innerHTML = '';
    });

    // Helper function to check if text represents a non-verbal event
    function isNonVerbalEvent(text) {
        return text.startsWith('[') && text.endsWith(']');
    }

    // Process the conversation data and create the graph
    function processConversationData(data) {
        // Reset
        cy.elements().remove();
        speakersList.innerHTML = '';
        relationsList.innerHTML = '';

        if (!data) {
            return;
        }

        // Handle different structures
        let edus = [];
        let relations = [];

        if (data.discourse_format) {
            edus = data.discourse_format.edus || [];
            relations = data.discourse_format.relations || [];
        } else if (data.edus) {
            edus = data.edus || [];
            relations = data.relations || [];
        } else {
            alert('Invalid JSON format. Could not find EDUs.');
            return;
        }

        // Collect all speakers for color assignment
        const speakers = new Set();
        edus.forEach(edu => {
            speakers.add(edu.speaker);
        });

        // Assign colors to speakers
        Array.from(speakers).forEach(speaker => {
            speakerColors[speaker] = stringToColor(speaker);
        });

        // Add nodes for each EDU
        edus.forEach((edu, index) => {
            const isNonVerbal = isNonVerbalEvent(edu.text);
            cy.add({
                group: 'nodes',
                data: {
                    id: index.toString(),
                    color: speakerColors[edu.speaker],
                    eduText: edu.text,
                    speaker: edu.speaker,
                    addressees: edu.addressees.join(', '),
                    shape: isNonVerbal ? 'diamond' : 'ellipse',
                    nodeSize: isNonVerbal ? 50 : 40,  // Bigger size for diamonds
                    opacity: isNonVerbal ? 0.8 : 1  // Slight transparency for non-verbal events
                },
                position: {
                    x: 300,  // Center x position
                    y: 100 + (index * 100)  // Vertical position based on index
                }
            });
        });

        // Add edges for each relation
        relations.forEach((relation, index) => {
            const relColor = relationColors[relation.type] || relationColors.default;
            cy.add({
                group: 'edges',
                data: {
                    id: 'e' + index + '_' + Date.now(), // Generate a unique ID for each edge
                    source: relation.x.toString(),
                    target: relation.y.toString(),
                    color: relColor,
                    relationType: relation.type
                }
            });
        });

        // Apply the preset layout
        cy.layout({
            name: 'preset',
            fit: true,
            padding: 50
        }).run();

        // Populate legend
        populateLegend(speakers);

        // Set up event listeners for nodes and edges
        setupEventListeners();

        // After setting up the graph, update the summary stats
        updateSummaryStats();
    }

    // Populate the legend with speakers and relation types
    function populateLegend(speakers) {
        // Speakers
        Array.from(speakers).forEach(speaker => {
            const item = document.createElement('div');
            item.className = 'color-item';

            const coloredText = document.createElement('span');
            coloredText.style.backgroundColor = speakerColors[speaker];
            coloredText.style.padding = '2px 8px';
            coloredText.style.borderRadius = '3px';
            coloredText.style.color = '#fff';
            coloredText.textContent = speaker;

            item.appendChild(coloredText);
            speakersList.appendChild(item);
        });

        // Relations
        Object.entries(relationColors).forEach(([type, color]) => {
            if (type === 'default') return;

            const item = document.createElement('div');
            item.className = 'color-item';

            const coloredText = document.createElement('span');
            coloredText.style.backgroundColor = color;
            coloredText.style.padding = '2px 8px';
            coloredText.style.borderRadius = '3px';
            coloredText.style.color = '#fff';
            coloredText.textContent = type;

            item.appendChild(coloredText);
            relationsList.appendChild(item);
        });
    }

    // Set up event listeners for nodes and edges
    function setupEventListeners() {
        // Clear selection when clicking on background
        cy.on('tap', function (event) {
            if (event.target === cy) {
                cy.elements().unselect();
                clearNodeInfo();
                clearEdgeInfo();
            }
        });

        // Node events
        cy.on('tap', 'node', function (e) {
            const node = e.target;
            // Unselect any selected edges
            cy.edges().unselect();
            displayNodeInfo(node);
        });

        // Edge events
        cy.on('tap', 'edge', function (e) {
            const edge = e.target;
            // Unselect any selected nodes
            cy.nodes().unselect();
            displayEdgeInfo(edge);
        });



        // Optional: Add hover effects for better UX
        cy.on('mouseover', 'node, edge', function (e) {
            const ele = e.target;
            if (!ele.selected()) {
                ele.style('opacity', 0.8);
            }
        });

        cy.on('mouseout', 'node, edge', function (e) {
            const ele = e.target;
            if (!ele.selected()) {
                ele.style('opacity', 1);
            }
        });
    }

    // Display node information in the info panel
    function displayNodeInfo(node) {
        const speakerColor = speakerColors[node.data('speaker')];
        eduText.innerHTML = '<span class="info-label">Text:</span> ' + node.data('eduText');
        eduSpeaker.innerHTML = '<span class="info-label">Speaker:</span> ' +
            `<span style="background-color: ${speakerColor}; padding: 2px 8px; border-radius: 3px; color: #fff;">` +
            node.data('speaker') + '</span>';

        // Handle addressees with colored backgrounds
        const addresseesList = node.data('addressees').split(', ').filter(a => a);
        if (addresseesList.length > 0) {
            const coloredAddressees = addresseesList.map(addressee => {
                const addresseeColor = speakerColors[addressee] || '#999999';
                return `<span style="background-color: ${addresseeColor}; padding: 2px 8px; border-radius: 3px; color: #fff; margin-right: 4px;">` +
                    addressee + '</span>';
            }).join(' ');
            eduAddressees.innerHTML = '<span class="info-label">Addressees:</span> ' + coloredAddressees;
        } else {
            eduAddressees.innerHTML = '<span class="info-label">Addressees:</span> None';
        }

        // No action buttons
    }



    // Display edge information in the info panel
    function displayEdgeInfo(edge) {
        const sourceNode = cy.getElementById(edge.data('source'));
        const targetNode = cy.getElementById(edge.data('target'));
        const relationColor = relationColors[edge.data('relationType')] || relationColors.default;
        const relationTypeValue = edge.data('relationType');

        relationType.innerHTML = '<span class="info-label">Type:</span> ' +
            `<span style="background-color: ${relationColor}; padding: 2px 8px; border-radius: 3px; color: #fff;">` +
            relationTypeValue + '</span>';
        relationSource.innerHTML = '<span class="info-label">Source EDU:</span> ' + sourceNode.data('eduText');
        relationTarget.innerHTML = '<span class="info-label">Target EDU:</span> ' + targetNode.data('eduText');
    }



    // Clear node information
    function clearNodeInfo() {
        eduText.innerHTML = '';
        eduSpeaker.innerHTML = '';
        eduAddressees.innerHTML = '';

        // Remove action buttons if they exist
        const actionButtons = document.querySelector('#node-info .action-buttons');
        if (actionButtons) {
            actionButtons.remove();
        }
    }

    // Clear edge information
    function clearEdgeInfo() {
        relationType.innerHTML = '';
        relationSource.innerHTML = '';
        relationTarget.innerHTML = '';

        // Remove action buttons if they exist
        const actionButtons = document.querySelector('#edge-info .action-buttons');
        if (actionButtons) {
            actionButtons.remove();
        }
    }

    // Clear all info panels
    function clearInfoPanels() {
        clearNodeInfo();
        clearEdgeInfo();
        // Unselect all elements
        if (cy) {
            cy.elements().unselect();
        }
        totalRelations.innerHTML = '';
        totalNodes.innerHTML = '';
        backEdgesCount.innerHTML = '';
        backEdgesList.innerHTML = '';
        orphanedNodesCount.innerHTML = '';
        orphanedNodesList.innerHTML = '';
        orphanedClustersCount.innerHTML = '';
        orphanedClustersList.innerHTML = '';
        relationCountsList.innerHTML = '';
    }

    // Update summary statistics
    function updateSummaryStats() {
        // Count relations and nodes
        const numRelations = cy.edges().length;
        const numNodes = cy.nodes().length;

        // Count each relation type
        const relationCounts = {};
        cy.edges().forEach(edge => {
            const type = edge.data('relationType');
            relationCounts[type] = (relationCounts[type] || 0) + 1;
        });

        // Find back edges (relations that point to earlier nodes)
        const backEdges = cy.edges().filter(edge => {
            const sourceId = parseInt(edge.data('source'));
            const targetId = parseInt(edge.data('target'));
            return targetId < sourceId;
        });

        // Find orphaned nodes (nodes without any connections)
        const orphanedNodes = cy.nodes().filter(node => node.degree(true) === 0);

        // Find connected components (clusters)
        const clusters = [];
        const visitedNodes = new Set();

        cy.nodes().forEach(node => {
            if (!visitedNodes.has(node.id())) {
                const cluster = [];
                const queue = [node];

                while (queue.length > 0) {
                    const currentNode = queue.shift();
                    if (!visitedNodes.has(currentNode.id())) {
                        visitedNodes.add(currentNode.id());
                        cluster.push(currentNode);

                        currentNode.neighborhood('node').forEach(neighbor => {
                            if (!visitedNodes.has(neighbor.id())) {
                                queue.push(neighbor);
                            }
                        });
                    }
                }

                clusters.push(cluster);
            }
        });

        // Sort clusters by size (largest first)
        clusters.sort((a, b) => b.length - a.length);

        // Get orphaned clusters (all except the largest one)
        const orphanedClusters = clusters.slice(1);

        // Update the display
        totalRelations.innerHTML = `<span class="info-label">Total Relations:</span> ${numRelations}`;
        totalNodes.innerHTML = `<span class="info-label">Total Nodes:</span> ${numNodes}`;


        // Update back edges section
        backEdgesCount.innerHTML = `<span class="info-label">Back Edges:</span> ${backEdges.length}`;
        if (backEdges.length > 0) {
            backEdgesList.innerHTML = backEdges.map(edge => {
                const sourceId = edge.data('source');
                const targetId = edge.data('target');
                const relType = edge.data('relationType');
                const relationColor = relationColors[relType] || relationColors.default;

                return `<div class="back-edge-item">
                        <span class="clickable-node link-style" data-node-id="${sourceId}">[${sourceId}]</span> → 
                        <span class="clickable-node link-style" data-node-id="${targetId}">[${targetId}]</span>
                        ...
                    </div>`;
            }).join('');
        } else {
            backEdgesList.innerHTML = '';
        }

        // Update relation counts section
        if (Object.keys(relationCounts).length > 0) {
            // Initialize counts for all possible relations
            const allRelationCounts = {};
            Object.keys(relationColors).forEach(type => {
                if (type !== 'default') {
                    allRelationCounts[type] = 0;
                }
            });
            // Add actual counts
            Object.entries(relationCounts).forEach(([type, count]) => {
                allRelationCounts[type] = count;
            });

            // Collect all edges for each relation type
            const relationEdges = {};
            cy.edges().forEach(edge => {
                const type = edge.data('relationType');
                if (!relationEdges[type]) relationEdges[type] = [];
                relationEdges[type].push({
                    source: edge.data('source'),
                    target: edge.data('target'),
                    sourceText: cy.getElementById(edge.data('source')).data('eduText'),
                    targetText: cy.getElementById(edge.data('target')).data('eduText')
                });
            });

            const sortedRelations = Object.entries(allRelationCounts).sort((a, b) => b[1] - a[1]); // Sort by count
            relationCountsList.innerHTML = sortedRelations.map(([type, count]) => {
                const color = relationColors[type] || relationColors.default;
                const edges = relationEdges[type] || [];
                return `
                    <div class="relation-count-item">
                        <div class="relation-header" onclick="this.parentElement.classList.toggle('expanded')">
                            <span style="background-color: ${color}; padding: 2px 8px; border-radius: 3px; color: #fff; margin-right: 8px;">
                                ${type}
                            </span>
                            <span class="count">${count}</span>
                            <span class="expand-icon">▼</span>
                        </div>
                        <div class="relation-details">
                            ${edges.map(edge => `
                                <div class="edge-item">
                                    <span class="clickable-node link-style" data-node-id="${edge.source}">[${edge.source}]</span> → 
                                    <span class="clickable-node link-style" data-node-id="${edge.target}">[${edge.target}]</span>
                                    <div class="edge-text">
                                        <div>"${edge.sourceText.substring(0, 50)}${edge.sourceText.length > 50 ? '...' : ''}"</div>
                                        <div>"${edge.targetText.substring(0, 50)}${edge.targetText.length > 50 ? '...' : ''}"</div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>`;
            }).join('');
        } else {
            // Show all relations with zero count if no relations exist
            const zeroCountRelations = Object.keys(relationColors)
                .filter(type => type !== 'default')
                .map(type => {
                    const color = relationColors[type];
                    return `
                        <div class="relation-count-item">
                            <div class="relation-header">
                                <span style="background-color: ${color}; padding: 2px 8px; border-radius: 3px; color: #fff; margin-right: 8px;">
                                    ${type}
                                </span>
                                <span class="count">0</span>
                            </div>
                        </div>`;
                }).join('');
            relationCountsList.innerHTML = zeroCountRelations;
        }

        // Update orphaned nodes section
        orphanedNodesCount.innerHTML = `<span class="info-label">Orphaned Nodes:</span> ${orphanedNodes.length}`;
        if (orphanedNodes.length > 0) {
            orphanedNodesList.innerHTML = '<div class="info-label">List:</div>' +
                orphanedNodes.map(node =>
                    `<div class="orphaned-item">
                        <span class="clickable-node link-style" data-node-id="${node.id()}">[${node.id()}]</span> 
                        ${node.data('eduText').substring(0, 50)}${node.data('eduText').length > 50 ? '...' : ''}
                    </div>`
                ).join('');
        } else {
            orphanedNodesList.innerHTML = '';
        }

        // Update orphaned clusters section
        orphanedClustersCount.innerHTML = `<span class="info-label">Orphaned Clusters:</span> ${orphanedClusters.length}`;
        if (orphanedClusters.length > 0) {
            orphanedClustersList.innerHTML = '<div class="info-label">List:</div>' +
                orphanedClusters.map((cluster, index) =>
                    `<div class="cluster-group">
                        <div>Cluster ${index + 1} (${cluster.length} nodes):</div>
                        ${cluster.map(node =>
                        `<div class="orphaned-item">
                                <span class="clickable-node link-style" data-node-id="${node.id()}">[${node.id()}]</span> 
                                ${node.data('eduText').substring(0, 50)}${node.data('eduText').length > 50 ? '...' : ''}
                            </div>`
                    ).join('')}
                    </div>`
                ).join('');
        } else {
            orphanedClustersList.innerHTML = '';
        }
    }



    // Add this code inside your main DOMContentLoaded listener
    summaryModal.addEventListener('click', function (event) {
        // Check if a clickable-node span was clicked
        const target = event.target.closest('.clickable-node');

        if (target) {
            const nodeId = target.dataset.nodeId; // Get the ID from the data-node-id attribute
            if (nodeId) {
                focusOnNode(nodeId);

                // Optional: Close the modal after focusing
                summaryModal.style.display = 'none';
            }
        }
    });
    // --- File Summary Logic ---
    const fileSummaryBtn = document.getElementById('fileSummaryBtn');
    const fileSummaryModal = document.getElementById('fileSummaryModal');
    const closeFileSummaryBtn = document.getElementById('closeFileSummary');
    const fileSummaryContent = document.getElementById('file-summary-content');

    if (fileSummaryBtn) {
        fileSummaryBtn.addEventListener('click', function () {
            if (!loadedData) {
                alert('Please load a JSON file first.');
                return;
            }
            const stats = calculateFileStats(loadedData);
            fileSummaryContent.textContent = JSON.stringify(stats, null, 2);
            fileSummaryModal.style.display = 'block';
        });
    }

    if (closeFileSummaryBtn) {
        closeFileSummaryBtn.addEventListener('click', function () {
            fileSummaryModal.style.display = 'none';
        });
    }

    function getPercentile(sortedArr, percentile) {
        if (sortedArr.length === 0) return 0;
        const index = (percentile / 100) * (sortedArr.length - 1);
        const lower = Math.floor(index);
        const upper = Math.ceil(index);
        const weight = index - lower;
        if (upper === lower) return sortedArr[lower];
        return sortedArr[lower] * (1 - weight) + sortedArr[upper] * weight;
    }

    function calculateStats(arr) {
        if (arr.length === 0) return { mean: 0, min: 0, max: 0, Q1: 0, median: 0, Q3: 0 };
        const sorted = [...arr].sort((a, b) => a - b);
        const sum = sorted.reduce((a, b) => a + b, 0);
        const mean = sum / sorted.length;
        const min = sorted[0];
        const max = sorted[sorted.length - 1];
        const median = getPercentile(sorted, 50);
        const Q1 = getPercentile(sorted, 25);
        const Q3 = getPercentile(sorted, 75);
        return { mean, min, max, Q1, median, Q3 };
    }

    function calculateFileStats(data) {
        const conversations = Array.isArray(data) ? data : [data];

        let total_num_edus = 0;
        let total_num_relations = 0;
        let total_num_speakers = 0;
        let total_num_non_verbal_actions = 0;
        let total_num_multi_parent_nodes = 0;
        let total_num_multi_child_nodes = 0;

        const num_edus_arr = [];
        const num_relations_arr = [];
        const num_speakers_arr = [];
        const num_non_verbal_actions_arr = [];
        const num_multi_parent_nodes_arr = [];
        const num_multi_child_nodes_arr = [];

        const relation_distances_arr = [];
        const num_addressees_arr = [];

        const relation_types_map = {};
        const multi_addressees_map = {};
        const relation_distances_distribution_map = {};
        const relation_distances_distribution_by_type = {};

        const allSpeakers = new Set();

        conversations.forEach(conv => {
            const edus = conv.edus || (conv.discourse_format ? conv.discourse_format.edus : []) || [];
            const relations = conv.relations || (conv.discourse_format ? conv.discourse_format.relations : []) || [];

            total_num_edus += edus.length;
            num_edus_arr.push(edus.length);

            const convSpeakers = new Set();
            let nonVerbalCount = 0;

            edus.forEach((edu, index) => {
                if (edu.speaker) {
                    convSpeakers.add(edu.speaker);
                    allSpeakers.add(edu.speaker);
                }

                if (isNonVerbalEvent(edu.text)) {
                    nonVerbalCount++;
                }

                const addressees = edu.addressees || [];
                let countKey = "";
                if (addressees.length === 1 && addressees[0].toLowerCase() === 'everyone') {
                    countKey = "everyone";
                } else {
                    countKey = addressees.length.toString();
                }
                multi_addressees_map[countKey] = (multi_addressees_map[countKey] || 0) + 1;
                num_addressees_arr.push(addressees.length);
            });

            num_speakers_arr.push(convSpeakers.size); // Per-convo unique speakers
            num_non_verbal_actions_arr.push(nonVerbalCount);

            // Accumulate global non-verbal count
            total_num_non_verbal_actions += nonVerbalCount;

            total_num_relations += relations.length;
            num_relations_arr.push(relations.length);

            const inDegree = new Array(edus.length).fill(0);
            const outDegree = new Array(edus.length).fill(0);

            relations.forEach(rel => {
                relation_types_map[rel.type] = (relation_types_map[rel.type] || 0) + 1;

                if (rel.y !== undefined) inDegree[rel.y]++;
                if (rel.x !== undefined) outDegree[rel.x]++;

                if (rel.x !== undefined && rel.y !== undefined) {
                    const dist = Math.abs(rel.y - rel.x);
                    relation_distances_arr.push(dist);

                    relation_distances_distribution_map[dist] = (relation_distances_distribution_map[dist] || 0) + 1;

                    const typeKey = `relation_distances_distribution_${rel.type.toLowerCase()}`;
                    if (!relation_distances_distribution_by_type[typeKey]) {
                        relation_distances_distribution_by_type[typeKey] = {};
                    }
                    relation_distances_distribution_by_type[typeKey][dist] = (relation_distances_distribution_by_type[typeKey][dist] || 0) + 1;
                }
            });

            let multiParent = 0;
            let multiChild = 0;
            inDegree.forEach(d => { if (d > 1) multiParent++; });
            outDegree.forEach(d => { if (d > 1) multiChild++; });

            total_num_multi_parent_nodes += multiParent;
            total_num_multi_child_nodes += multiChild;
            num_multi_parent_nodes_arr.push(multiParent);
            if (edus.length > 0) num_multi_child_nodes_arr.push(multiChild);
        });

        // Use global unique speakers for the total count, but statistics use per-convo counts
        total_num_speakers = allSpeakers.size;

        return {
            total_num_edus,
            total_num_relations,
            total_num_speakers,
            total_num_non_verbal_actions,
            total_num_multi_parent_nodes,
            total_num_multi_child_nodes,
            num_edus: calculateStats(num_edus_arr),
            num_relations: calculateStats(num_relations_arr),
            num_speakers: calculateStats(num_speakers_arr),
            num_non_verbal_actions: calculateStats(num_non_verbal_actions_arr),
            num_multi_parent_nodes: calculateStats(num_multi_parent_nodes_arr),
            num_multi_child_nodes: calculateStats(num_multi_child_nodes_arr),
            relation_distance: calculateStats(relation_distances_arr),
            num_addressees: calculateStats(num_addressees_arr),
            relation_types: relation_types_map,
            multi_addressees: multi_addressees_map,
            relation_distances_distribution: relation_distances_distribution_map,
            ...relation_distances_distribution_by_type
        };
    }

});

