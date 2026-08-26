import express from 'express';
import cors from 'cors';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';
import Razorpay from 'razorpay';

dotenv.config();

const __dirname = dirname(fileURLToPath(import.meta.url));
const app = express();

app.use(cors());
app.use(express.json());

app.use((req, res, next) => {
    console.log(`${req.method} ${req.url}`);
    next();
});

// In-memory data store
let products = [
    { sku: 'SKU-ELEC-001', name: 'Wireless Mouse', price_paise: 59900, stock: 5, reorder_threshold: 10, category: 'Electronics' },
    { sku: 'SKU-ELEC-002', name: 'Mechanical Keyboard', price_paise: 249900, stock: 3, reorder_threshold: 5, category: 'Electronics' },
    { sku: 'SKU-ELEC-003', name: 'USB-C Hub', price_paise: 189900, stock: 8, reorder_threshold: 10, category: 'Electronics' },
    { sku: 'SKU-ELEC-004', name: 'Webcam HD 1080p', price_paise: 149900, stock: 2, reorder_threshold: 5, category: 'Electronics' },
    { sku: 'SKU-OFFC-001', name: 'A4 Paper Ream (500 sheets)', price_paise: 34900, stock: 15, reorder_threshold: 20, category: 'Office Supplies' },
    { sku: 'SKU-OFFC-002', name: 'Whiteboard Markers (Pack of 10)', price_paise: 19900, stock: 25, reorder_threshold: 30, category: 'Office Supplies' },
    { sku: 'SKU-OFFC-003', name: 'Desk Organizer', price_paise: 79900, stock: 4, reorder_threshold: 8, category: 'Office Supplies' },
    { sku: 'SKU-TECH-001', name: 'HDMI Cable 2m', price_paise: 29900, stock: 12, reorder_threshold: 15, category: 'Tech Accessories' },
    { sku: 'SKU-TECH-002', name: 'Laptop Stand Adjustable', price_paise: 199900, stock: 6, reorder_threshold: 8, category: 'Tech Accessories' },
    { sku: 'SKU-TECH-003', name: 'Surge Protector 6-Outlet', price_paise: 89900, stock: 7, reorder_threshold: 10, category: 'Tech Accessories' },
];

let ledger = [];

// Dynamic Pricing Algorithm Helper
function getProductPricing(product) {
    if (product.stock > 0 && product.stock <= 2) {
        return {
            effective_price_paise: Math.round(product.price_paise * 1.25),
            pricing_type: 'surge',
            pricing_label: '⚡ SURGE (+25%)',
            multiplier: 1.25,
            base_price_paise: product.price_paise
        };
    } else if (product.stock >= 15) {
        return {
            effective_price_paise: Math.round(product.price_paise * 0.85),
            pricing_type: 'discount',
            pricing_label: '🏷️ FLASH SALE (-15%)',
            multiplier: 0.85,
            base_price_paise: product.price_paise
        };
    }
    return {
        effective_price_paise: product.price_paise,
        pricing_type: 'standard',
        pricing_label: '✓ STABLE',
        multiplier: 1.0,
        base_price_paise: product.price_paise
    };
}

app.get('/api', (req, res) => {
    res.json({
        status: "online",
        service: "Autonomous Agentic Commerce Engine",
        version: "1.1.0",
        endpoints: {
            "/api/inventory": "GET - Agent-readable product catalog with dynamic surge pricing",
            "/api/checkout": "POST - Execute purchase transaction",
            "/api/restock": "POST - Execute supplier replenishment",
            "/api/ledger": "GET - View audit trail",
            "/api/analytics": "GET - View real-time M2M financial analytics"
        }
    });
});

app.get('/api/inventory', (req, res) => {
    const enrichedProducts = products.map(p => {
        const pricing = getProductPricing(p);
        return {
            ...p,
            effective_price_paise: pricing.effective_price_paise,
            pricing_type: pricing.pricing_type,
            pricing_label: pricing.pricing_label,
            multiplier: pricing.multiplier
        };
    });
    res.json({
        products: enrichedProducts,
        timestamp: new Date().toISOString()
    });
});

app.get('/api/inventory/:sku', (req, res) => {
    const product = products.find(p => p.sku === req.params.sku);
    if (!product) {
        return res.status(404).json({ detail: "Product not found" });
    }
    const pricing = getProductPricing(product);
    res.json({
        ...product,
        effective_price_paise: pricing.effective_price_paise,
        pricing_type: pricing.pricing_type,
        pricing_label: pricing.pricing_label
    });
});

let razorpayClient = null;
try {
    if (process.env.RAZORPAY_KEY_ID && process.env.RAZORPAY_KEY_SECRET) {
        razorpayClient = new Razorpay({
            key_id: process.env.RAZORPAY_KEY_ID,
            key_secret: process.env.RAZORPAY_KEY_SECRET
        });
        console.log("Razorpay SDK initialized successfully.");
    }
} catch (e) {
    console.error("Failed to initialize Razorpay:", e);
}

app.post('/api/checkout', async (req, res) => {
    const { items, trigger_reason } = req.body;
    
    let total_paise = 0;
    let skus_list = [];
    
    try {
        if (!items || !Array.isArray(items)) {
            throw new Error("Invalid request");
        }
        
        // Validation and calculate
        for (const item of items) {
            const product = products.find(p => p.sku === item.sku);
            if (!product) {
                throw new Error(`Product not found: ${item.sku}`);
            }
            if (product.stock < item.quantity) {
                throw new Error(`Insufficient stock for ${item.sku}`);
            }
            const pricing = getProductPricing(product);
            total_paise += pricing.effective_price_paise * item.quantity;
            skus_list.push(item.sku);
        }
        
        // Guardrails check (let's say max 1000000 paise - configurable via env? We will just hardcode)
        if (total_paise > 500000) {
            throw new Error("SpendingLimitExceeded");
        }
        
        // Deduct stock
        for (const item of items) {
            const product = products.find(p => p.sku === item.sku);
            product.stock -= item.quantity;
        }
        
        let orderId = `mock_order_${Math.random().toString(36).substr(2, 9)}`;
        const receipt = `rcpt_${Math.random().toString(36).substr(2, 9)}`;
        
        if (razorpayClient) {
            try {
                const rzpOrder = await razorpayClient.orders.create({
                    amount: total_paise,
                    currency: "INR",
                    receipt: receipt
                });
                orderId = rzpOrder.id;
            } catch (rzpErr) {
                throw new Error(`Razorpay API Error: ${rzpErr.error?.description || rzpErr.message || "Unknown error"}`);
            }
        }
        
        const entry = {
            id: ledger.length + 1,
            timestamp: new Date().toISOString(),
            type: "sale",
            trigger_reason: trigger_reason || 'manual_checkout',
            skus: skus_list,
            cart_value_paise: total_paise,
            razorpay_order_id: orderId,
            status: "success",
            error_message: null
        };
        ledger.push(entry);
        
        res.json({
            order_id: orderId,
            amount_paise: total_paise,
            currency: 'INR',
            receipt: receipt,
            status: 'created'
        });
        
    } catch (e) {
        const errorMsg = e.message;
        
        if (errorMsg === "SpendingLimitExceeded") {
            return res.status(422).json({
                error: "SpendingLimitExceeded",
                detail: "Spending limit exceeded",
                max_allowed_paise: 500000,
                attempted_paise: total_paise
            });
        }
        
        const entry = {
            id: ledger.length + 1,
            timestamp: new Date().toISOString(),
            type: "sale",
            trigger_reason: trigger_reason || 'manual_checkout',
            skus: skus_list,
            cart_value_paise: total_paise,
            razorpay_order_id: null,
            status: "failed",
            error_message: errorMsg
        };
        ledger.push(entry);
        
        res.status(400).json({ detail: errorMsg });
    }
});

app.post('/api/restock', async (req, res) => {
    const { items, trigger_reason } = req.body;
    
    let total_paise = 0;
    let skus_list = [];
    
    try {
        if (!items || !Array.isArray(items)) {
            throw new Error("Invalid request");
        }
        
        // Validation and calculate
        for (const item of items) {
            const product = products.find(p => p.sku === item.sku);
            if (!product) {
                throw new Error(`Product not found: ${item.sku}`);
            }
            total_paise += product.price_paise * item.quantity; // We assume supplier cost is same for simplicity, or slightly lower? Let's use 70% of price as cost
            skus_list.push(item.sku);
        }
        
        const cost_paise = Math.floor(total_paise * 0.7); // 30% margin
        
        // Guardrails check
        if (cost_paise > 500000) {
            throw new Error("SpendingLimitExceeded");
        }
        
        // Add stock
        for (const item of items) {
            const product = products.find(p => p.sku === item.sku);
            product.stock += item.quantity;
        }
        
        let orderId = `mock_supp_order_${Math.random().toString(36).substr(2, 9)}`;
        const receipt = `rcpt_${Math.random().toString(36).substr(2, 9)}`;
        
        if (razorpayClient) {
            try {
                // Conceptually, paying supplier via Razorpay route
                const rzpOrder = await razorpayClient.orders.create({
                    amount: cost_paise,
                    currency: "INR",
                    receipt: receipt
                });
                orderId = rzpOrder.id;
            } catch (rzpErr) {
                throw new Error(`Razorpay API Error: ${rzpErr.error?.description || rzpErr.message || "Unknown error"}`);
            }
        }
        
        const entry = {
            id: ledger.length + 1,
            timestamp: new Date().toISOString(),
            type: "expense",
            trigger_reason: trigger_reason || 'internal_restock',
            skus: skus_list,
            cart_value_paise: cost_paise,
            razorpay_order_id: orderId,
            status: "success",
            error_message: null
        };
        ledger.push(entry);
        
        res.json({
            order_id: orderId,
            amount_paise: cost_paise,
            currency: 'INR',
            receipt: receipt,
            status: 'created'
        });
        
    } catch (e) {
        const errorMsg = e.message;
        
        if (errorMsg === "SpendingLimitExceeded") {
            return res.status(422).json({
                error: "SpendingLimitExceeded",
                detail: "Restock spending limit exceeded",
                max_allowed_paise: 500000,
                attempted_paise: total_paise
            });
        }
        
        const entry = {
            id: ledger.length + 1,
            timestamp: new Date().toISOString(),
            type: "expense",
            trigger_reason: trigger_reason || 'internal_restock',
            skus: skus_list,
            cart_value_paise: total_paise,
            razorpay_order_id: null,
            status: "failed",
            error_message: errorMsg
        };
        ledger.push(entry);
        
        res.status(400).json({ detail: errorMsg });
    }
});

app.get('/api/ledger', (req, res) => {
    res.json(ledger);
});

app.get('/api/analytics', (req, res) => {
    let totalRevenue = 0;
    let totalExpenses = 0;
    let successfulSales = 0;
    let successfulRestocks = 0;
    let failedOrders = 0;

    let history = [];
    let runningRevenue = 0;
    let runningExpenses = 0;

    ledger.forEach(entry => {
        if (entry.status === 'success') {
            if (entry.type === 'sale') {
                totalRevenue += entry.cart_value_paise;
                runningRevenue += entry.cart_value_paise;
                successfulSales++;
            } else if (entry.type === 'expense') {
                totalExpenses += entry.cart_value_paise;
                runningExpenses += entry.cart_value_paise;
                successfulRestocks++;
            }
        } else {
            failedOrders++;
        }
        history.push({
            id: entry.id,
            timestamp: entry.timestamp,
            type: entry.type,
            status: entry.status,
            revenue: runningRevenue / 100,
            expenses: runningExpenses / 100,
            profit: (runningRevenue - runningExpenses) / 100
        });
    });

    res.json({
        metrics: {
            total_revenue_paise: totalRevenue,
            total_expenses_paise: totalExpenses,
            net_profit_paise: totalRevenue - totalExpenses,
            successful_sales: successfulSales,
            successful_restocks: successfulRestocks,
            failed_orders: failedOrders,
            total_items_in_catalog: products.length,
            out_of_stock_count: products.filter(p => p.stock === 0).length,
            surge_pricing_count: products.filter(p => p.stock > 0 && p.stock <= 2).length
        },
        history: history
    });
});

// Serve frontend
app.use(express.static(join(__dirname, '../frontend')));
app.get('*', (req, res) => res.sendFile(join(__dirname, '../frontend/index.html')));

app.listen(3000, '0.0.0.0', () => {
    console.log('Server running on port 3000');
});
