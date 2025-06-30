const { spawn } = require('child_process');
const readline = require('readline');
const fs = require('fs');
const path = require('path');

class CustomSQLMCPAgent {
    constructor(mcpServerPath, connectionConfig) {
        this.mcpServerPath = mcpServerPath;
        this.connectionConfig = connectionConfig;
        this.mcpProcess = null;
        this.availableTools = [];
        this.pendingRequests = {};
        this.requestIdCounter = 1;

        this.rl = readline.createInterface({
            input: process.stdin,
            output: process.stdout
        });
    }

    async initialize() {
        console.log('🚀 Initializing Custom SQL MCP Agent...');

        try {
            // Create a temporary config file for the MCP server
            await this.createConfigFile();
            await this.startMCPServer();
            await this.sleep(3000); // Give server time to fully start
            await this.initializeMCPProtocol();
            await this.discoverTools();

            console.log('✅ MCP Agent initialized successfully!');
            console.log(`📊 Connected to database: ${this.connectionConfig.database}`);
            console.log(`🛠️  Available tools: ${this.availableTools.length}`);
        } catch (error) {
            console.error('❌ Failed to initialize MCP Agent:', error.message);
            throw error;
        }
    }

    async createConfigFile() {
        // Create a temporary configuration file that the MCP server can read
        const configPath = path.join(__dirname, 'temp_mcp_config.json');
        const config = {
            server: this.connectionConfig.server,
            database: this.connectionConfig.database,
            user: this.connectionConfig.user,
            password: this.connectionConfig.password,
            port: this.connectionConfig.port || 1433,
            options: {
                encrypt: this.connectionConfig.options?.encrypt !== false,
                trustServerCertificate: this.connectionConfig.options?.trustServerCertificate !== false
            }
        };

        fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
        this.configPath = configPath;
        console.log('📝 Created temporary config file:', configPath);
    }

    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    startMCPServer() {
        return new Promise((resolve, reject) => {
            // Pass the database configuration through environment variables AND arguments
            const env = { 
                ...process.env,
                // Standard environment variables
                MSSQL_SERVER: this.connectionConfig.server,
                MSSQL_USER: this.connectionConfig.user,
                MSSQL_PASSWORD: this.connectionConfig.password,
                MSSQL_DATABASE: this.connectionConfig.database,
                MSSQL_PORT: String(this.connectionConfig.port || 1433),
                MSSQL_ENCRYPT: String(this.connectionConfig.options?.encrypt !== false),
                MSSQL_TRUST_SERVER_CERTIFICATE: String(this.connectionConfig.options?.trustServerCertificate !== false),
                
                // Alternative patterns
                DB_SERVER: this.connectionConfig.server,
                DB_USER: this.connectionConfig.user,
                DB_PASSWORD: this.connectionConfig.password,
                DB_DATABASE: this.connectionConfig.database,
                DB_PORT: String(this.connectionConfig.port || 1433),
                
                // Connection string format
                DATABASE_URL: `Server=${this.connectionConfig.server};Database=${this.connectionConfig.database};User Id=${this.connectionConfig.user};Password=${this.connectionConfig.password};TrustServerCertificate=true;Encrypt=true;`
            };

            console.log('Starting MCP server with config:', {
                server: this.connectionConfig.server,
                database: this.connectionConfig.database,
                user: this.connectionConfig.user,
                serverPath: this.mcpServerPath
            });

            // Try to start the server with different argument patterns
            const args = [this.mcpServerPath];
            
            // Some MCP servers accept config as command line arguments
            if (this.configPath) {
                args.push('--config', this.configPath);
            }

            this.mcpProcess = spawn('node', args, {
                stdio: ['pipe', 'pipe', 'pipe'],
                env: env,
                cwd: path.dirname(this.mcpServerPath)
            });

            this.mcpProcess.on('error', (error) => {
                reject(new Error(`Failed to start MCP server: ${error.message}`));
            });

            this.mcpProcess.on('exit', (code, signal) => {
                if (code !== 0) {
                    console.error(`MCP server exited with code ${code}, signal ${signal}`);
                }
            });

            this.mcpProcess.stdout.on('data', (data) => {
                const output = data.toString();
                console.log('MCP Server Output:', output.trim());
                this.handleMCPResponse(output);
            });

            this.mcpProcess.stderr.on('data', (data) => {
                const error = data.toString();
                console.error('MCP Server Error:', error.trim());
                
                // Check for specific configuration errors
                if (error.includes('config.server') || error.includes('configuration')) {
                    reject(new Error(`MCP Server configuration error: ${error.trim()}`));
                }
            });

            // Wait for server to start
            setTimeout(() => resolve(), 2000);
        });
    }

    async initializeMCPProtocol() {
        console.log('Initializing MCP protocol...');
        const initMessage = {
            jsonrpc: '2.0',
            id: this.getNextRequestId(),
            method: 'initialize',
            params: {
                protocolVersion: '2024-11-05',
                capabilities: { 
                    roots: { listChanged: true }, 
                    sampling: {} 
                },
                clientInfo: { 
                    name: 'Custom SQL MCP Agent', 
                    version: '1.0.0' 
                }
            }
        };

        try {
            const response = await this.sendMCPMessage(initMessage);
            console.log('MCP protocol initialized:', response?.result ? 'Success' : 'Failed');
            
            // Send initialized notification
            const initializedMessage = {
                jsonrpc: '2.0',
                method: 'notifications/initialized',
                params: {}
            };
            
            this.sendMCPNotification(initializedMessage);
        } catch (error) {
            console.error('Failed to initialize MCP protocol:', error.message);
            throw error;
        }
    }

    getNextRequestId() {
        return this.requestIdCounter++;
    }

    async discoverTools() {
        console.log('Discovering available tools...');
        const toolsMessage = {
            jsonrpc: '2.0',
            id: this.getNextRequestId(),
            method: 'tools/list',
            params: {}
        };

        try {
            const response = await this.sendMCPMessage(toolsMessage);

            if (response?.result?.tools) {
                this.availableTools = response.result.tools;
                console.log('\n📋 Available Database Tools:');
                this.availableTools.forEach(tool => {
                    console.log(`   • ${tool.name}: ${tool.description}`);
                });
            } else {
                console.log('No tools discovered. Response:', JSON.stringify(response, null, 2));
                
                // Try alternative tool discovery methods
                await this.tryAlternativeToolDiscovery();
            }
        } catch (error) {
            console.error('Error discovering tools:', error.message);
            throw error;
        }
    }

    async tryAlternativeToolDiscovery() {
        console.log('Trying alternative tool discovery methods...');
        
        // Try different method names that might be used
        const methods = ['tools/list', 'list_tools', 'get_tools', 'capabilities'];
        
        for (const method of methods) {
            try {
                const response = await this.sendMCPMessage({
                    jsonrpc: '2.0',
                    id: this.getNextRequestId(),
                    method: method,
                    params: {}
                });
                
                if (response?.result) {
                    console.log(`Method ${method} returned:`, JSON.stringify(response.result, null, 2));
                }
            } catch (error) {
                console.log(`Method ${method} failed:`, error.message);
            }
        }
    }

    sendMCPMessage(message) {
        return new Promise((resolve, reject) => {
            const messageStr = JSON.stringify(message) + '\n';
            
            if (!this.mcpProcess || this.mcpProcess.killed) {
                reject(new Error('MCP process not available'));
                return;
            }

            console.log('Sending MCP message:', JSON.stringify(message, null, 2));

            this.mcpProcess.stdin.write(messageStr, (error) => {
                if (error) {
                    reject(error);
                } else {
                    this.pendingRequests[message.id] = { resolve, reject, timestamp: Date.now() };

                    // Set timeout for request
                    setTimeout(() => {
                        if (this.pendingRequests[message.id]) {
                            delete this.pendingRequests[message.id];
                            reject(new Error(`Request timeout for message ID: ${message.id}`));
                        }
                    }, 15000);
                }
            });
        });
    }

    sendMCPNotification(message) {
        const messageStr = JSON.stringify(message) + '\n';
        console.log('Sending MCP notification:', JSON.stringify(message, null, 2));
        
        if (this.mcpProcess && !this.mcpProcess.killed) {
            this.mcpProcess.stdin.write(messageStr);
        }
    }

    handleMCPResponse(data) {
        try {
            const lines = data.trim().split('\n');
            lines.forEach(line => {
                if (line.trim()) {
                    try {
                        const response = JSON.parse(line);
                        console.log('Received MCP response:', JSON.stringify(response, null, 2));
                        
                        // Handle responses with IDs (requests)
                        if (response.id && this.pendingRequests[response.id]) {
                            const { resolve } = this.pendingRequests[response.id];
                            resolve(response);
                            delete this.pendingRequests[response.id];
                        }
                        // Handle errors
                        else if (response.error) {
                            console.error('MCP Error Response:', response.error);
                            if (response.id && this.pendingRequests[response.id]) {
                                const { reject } = this.pendingRequests[response.id];
                                reject(new Error(response.error.message || JSON.stringify(response.error)));
                                delete this.pendingRequests[response.id];
                            }
                        }
                        // Handle notifications (no ID)
                        else if (response.method) {
                            console.log('MCP Notification:', response.method, response.params);
                        }
                    } catch (parseError) {
                        console.log('Non-JSON output from MCP server:', line);
                    }
                }
            });
        } catch (error) {
            console.error('Error handling MCP response:', error.message);
            console.error('Raw data:', data);
        }
    }

    async processNaturalLanguageQuery(userInput) {
        console.log(`\n🤔 Processing: "${userInput}"`);

        if (this.availableTools.length === 0) {
            console.log('❌ No tools available. Please check MCP server connection.');
            return;
        }

        const analysis = this.analyzeUserInput(userInput);
        console.log(`🎯 Intent: ${analysis.intent}`);
        console.log(`🗂️  Target Tables: ${analysis.tables.join(', ') || 'Auto-detect'}`);

        try {
            const result = await this.executeAnalysis(analysis);
            this.displayResults(result, userInput);
        } catch (error) {
            console.error('❌ Error processing query:', error.message);
        }
    }

    // Rest of the methods remain the same as in your original code
    analyzeUserInput(input) {
        const inputLower = input.toLowerCase();

        let intent = 'SELECT';
        if (/\b(show|list|get|find|select|display)\b/.test(inputLower)) intent = 'SELECT';
        else if (/\b(count|how many|total)\b/.test(inputLower)) intent = 'COUNT';
        else if (/\b(create|add|insert)\b/.test(inputLower)) intent = 'INSERT';
        else if (/\b(update|change|modify)\b/.test(inputLower)) intent = 'UPDATE';
        else if (/\b(delete|remove|drop)\b/.test(inputLower)) intent = 'DELETE';
        else if (/\b(describe|structure|schema|columns)\b/.test(inputLower)) intent = 'DESCRIBE';

        const tables = [];
        const tableKeywords = {
            'customers': ['customer', 'client', 'user'],
            'orders': ['order', 'purchase', 'sale'],
            'products': ['product', 'item'],
            'employees': ['employee', 'staff', 'worker'],
            'payments': ['payment', 'invoice', 'billing'],
            'support_tickets': ['ticket', 'issue', 'support']
        };

        Object.entries(tableKeywords).forEach(([table, keywords]) => {
            if (keywords.some(keyword => inputLower.includes(keyword))) {
                tables.push(table);
            }
        });

        const conditions = {};
        
        const locationMatch = inputLower.match(/(?:from|in)\s+([a-zA-Z\s]+?)(?:\s|$)/);
        if (locationMatch) {
            conditions.location = locationMatch[1].trim();
        }

        const limitMatch = inputLower.match(/(?:top|first|limit)\s+(\d+)/);
        if (limitMatch) {
            conditions.limit = parseInt(limitMatch[1]);
        }

        const statusMatch = inputLower.match(/(?:status|state)\s+(\w+)/);
        if (statusMatch) {
            conditions.status = statusMatch[1];
        }

        return { intent, tables, conditions, originalInput: input };
    }

    async executeAnalysis(analysis) {
        const { intent, tables, conditions } = analysis;

        try {
            switch (intent) {
                case 'SELECT':
                    return tables.length === 0 ?
                        await this.listAllTables() :
                        await this.readTableData(tables[0], conditions);

                case 'COUNT':
                    return tables.length > 0 ?
                        await this.countTableRecords(tables[0], conditions) :
                        await this.listAllTables();

                case 'DESCRIBE':
                    return tables.length > 0 ?
                        await this.describeTable(tables[0]) :
                        await this.listAllTables();

                default:
                    return await this.listAllTables();
            }
        } catch (error) {
            console.error('Error in executeAnalysis:', error.message);
            throw error;
        }
    }

    async listAllTables() {
        const toolName = this.findToolByName(['list_tables', 'list_table', 'show_tables', 'get_tables']);
        if (!toolName) {
            console.log('Available tools:', this.availableTools.map(t => t.name));
            throw new Error('No table listing tool found');
        }

        return await this.sendMCPMessage({
            jsonrpc: '2.0',
            id: this.getNextRequestId(),
            method: 'tools/call',
            params: {
                name: toolName,
                arguments: {}
            }
        });
    }

    async describeTable(tableName) {
        const toolName = this.findToolByName(['describe_table', 'table_schema', 'show_columns', 'get_schema']);
        if (!toolName) {
            throw new Error('No table description tool found');
        }

        return await this.sendMCPMessage({
            jsonrpc: '2.0',
            id: this.getNextRequestId(),
            method: 'tools/call',
            params: {
                name: toolName,
                arguments: { table_name: tableName }
            }
        });
    }

    async readTableData(tableName, conditions = {}) {
        const toolName = this.findToolByName(['read_data', 'query_table', 'select_data', 'query']);
        if (!toolName) {
            throw new Error('No data reading tool found');
        }

        let query = `SELECT * FROM ${tableName}`;
        if (conditions.where_clause) {
            query += ` WHERE ${conditions.where_clause}`;
        }
        if (conditions.limit) {
            query += ` LIMIT ${conditions.limit}`;
        }

        const args = { query };

        
        if (conditions.limit) {
            args.limit = conditions.limit;
        }
        
        if (conditions.location) {
            args.where_clause = `city LIKE '%${conditions.location}%' OR state LIKE '%${conditions.location}%'`;
        }
        
        if (conditions.status) {
            const statusClause = `status = '${conditions.status}'`;
            args.where_clause = args.where_clause ? 
                `(${args.where_clause}) AND ${statusClause}` : statusClause;
        }

        return await this.sendMCPMessage({
            jsonrpc: '2.0',
            id: this.getNextRequestId(),
            method: 'tools/call',
            params: {
                name: toolName,
                arguments: args
            }
        });
    }

    async countTableRecords(tableName, conditions = {}) {
        const toolName = this.findToolByName(['read_data', 'query_table', 'select_data', 'query']);
        if (!toolName) {
            throw new Error('No data reading tool found');
        }

        let query = `SELECT COUNT(*) as total_count FROM ${tableName}`;
        if (conditions.where_clause) {
            query += ` WHERE ${conditions.where_clause}`;
        }

        const args = { query };

        if (conditions.location) {
            args.where_clause = `city LIKE '%${conditions.location}%' OR state LIKE '%${conditions.location}%'`;
        }

        if (conditions.status) {
            const statusClause = `status = '${conditions.status}'`;
            args.where_clause = args.where_clause ? 
                `(${args.where_clause}) AND ${statusClause}` : statusClause;
        }

        return await this.sendMCPMessage({
            jsonrpc: '2.0',
            id: this.getNextRequestId(),
            method: 'tools/call',
            params: {
                name: toolName,
                arguments: args
            }
        });
    }

    findToolByName(possibleNames) {
        for (const name of possibleNames) {
            const tool = this.availableTools.find(t => t.name === name);
            if (tool) return tool.name;
        }
        return null;
    }

    displayResults(result, originalQuery) {
        console.log('\n📊 Results:');
        console.log('─'.repeat(50));

        if (result?.error) {
            console.log('❌ Error:', result.error.message || result.error);
        } else if (result?.result?.content) {
            const content = result.result.content;
            if (Array.isArray(content)) {
                content.forEach(item => {
                    if (item.type === 'text') {
                        console.log(item.text);
                    } else {
                        console.log(JSON.stringify(item, null, 2));
                    }
                });
            } else if (typeof content === 'string') {
                console.log(content);
            } else {
                console.log(JSON.stringify(content, null, 2));
            }
        } else {
            console.log('No results returned');
            console.log('Full response:', JSON.stringify(result, null, 2));
        }

        console.log('─'.repeat(50));
    }

    async startInteractiveSession() {
        console.log('\n🎯 MCP Agent Ready!');
        console.log('💬 Try asking things like:');
        console.log('   • "Show me all tables"');
        console.log('   • "List orders from California"');
        console.log('   • "How many tickets are open?"');
        console.log('   • "Describe the customers table"');
        console.log('   • Type "tools" to see available tools');
        console.log('   • Type "exit" to quit\n');

        this.rl.setPrompt('🗣️  You: ');
        this.rl.prompt();

        this.rl.on('line', async (input) => {
            const trimmedInput = input.trim();

            if (trimmedInput.toLowerCase() === 'exit') {
                console.log('👋 Closing MCP Agent...');
                this.cleanup();
                return;
            }

            if (trimmedInput.toLowerCase() === 'tools') {
                console.log('\n🛠️ Available Tools:');
                if (this.availableTools.length === 0) {
                    console.log('   No tools discovered yet. This might indicate a connection issue.');
                } else {
                    this.availableTools.forEach(tool => {
                        console.log(`   • ${tool.name}: ${tool.description}`);
                    });
                }
                console.log('');
                this.rl.prompt();
                return;
            }

            if (trimmedInput.toLowerCase() === 'debug') {
                console.log('\n🔍 Debug Information:');
                console.log('MCP Process alive:', this.mcpProcess && !this.mcpProcess.killed);
                console.log('Available tools:', this.availableTools.length);
                console.log('Pending requests:', Object.keys(this.pendingRequests).length);
                console.log('');
                this.rl.prompt();
                return;
            }

            if (trimmedInput) {
                await this.processNaturalLanguageQuery(trimmedInput);
            }

            console.log('\n');
            this.rl.prompt();
        });

        this.rl.on('SIGINT', () => {
            console.log('\n👋 Shutting down...');
            this.cleanup();
        });
    }

    cleanup() {
        console.log('Cleaning up resources...');
        
        // Clean up temporary config file
        if (this.configPath && fs.existsSync(this.configPath)) {
            try {
                fs.unlinkSync(this.configPath);
                console.log('Removed temporary config file');
            } catch (error) {
                console.log('Error removing config file:', error.message);
            }
        }
        
        if (this.mcpProcess && !this.mcpProcess.killed) {
            this.mcpProcess.kill('SIGTERM');
            setTimeout(() => {
                if (!this.mcpProcess.killed) {
                    this.mcpProcess.kill('SIGKILL');
                }
            }, 5000);
        }
        if (this.rl) {
            this.rl.close();
        }
        process.exit(0);
    }
}

// ─────────────────────────────────────────────────────────────
// MAIN FUNCTION
// ─────────────────────────────────────────────────────────────
async function main() {
    const mcpServerPath = 'D:/MCP_server_client/SQL-AI-samples/MssqlMcp/Node/dist/index.js';

    const connectionConfig = {
        user: 'sa',
        password: 'password',   // Update with your actual password
        server: 'localhost',
        database: 'testdb',
        port: 1433,
        options: {
            encrypt: true,
            trustServerCertificate: true
        }
    };

    console.log('🎯 Starting Custom SQL MCP Agent...');
    console.log('📋 Configuration:');
    console.log(`   Server: ${connectionConfig.server}:${connectionConfig.port}`);
    console.log(`   Database: ${connectionConfig.database}`);
    console.log(`   User: ${connectionConfig.user}`);
    console.log(`   MCP Server: ${mcpServerPath}`);

    const agent = new CustomSQLMCPAgent(mcpServerPath, connectionConfig);

    try {
        await agent.initialize();
        await agent.startInteractiveSession();
    } catch (error) {
        console.error('Failed to start agent:', error.message);
        console.error('Stack trace:', error.stack);
        
        console.log('\n🔍 Troubleshooting Tips:');
        console.log('1. Verify the MCP server path exists and is correct');
        console.log('2. Check that your database is running and accessible');
        console.log('3. Verify your database credentials are correct');
        console.log('4. Make sure the MCP server supports the expected configuration format');
        console.log('5. Check if the MCP server needs to be built first (npm run build)');
        
        process.exit(1);
    }
}

// Handle process termination gracefully
process.on('SIGINT', () => {
    console.log('\n👋 Shutting down...');
    process.exit(0);
});

process.on('SIGTERM', () => {
    console.log('\n👋 Shutting down...');
    process.exit(0);
});

process.on('uncaughtException', (error) => {
    console.error('Uncaught Exception:', error);
    process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled Rejection at:', promise, 'reason:', reason);
    process.exit(1);
});

if (require.main === module) {
    main().catch(console.error);
}

module.exports = { CustomSQLMCPAgent };