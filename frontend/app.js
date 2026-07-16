const { useState, useEffect, useRef } = React;

function App() {
    // State Variables
    const [events, setEvents] = useState([]);
    const [tasks, setTasks] = useState([]);
    const [settings, setSettings] = useState({
        sleep_start: "22:00",
        sleep_end: "06:00",
        study_start: "08:00",
        study_end: "20:00",
        timezone: "UTC"
    });
    
    const [chatMessages, setChatMessages] = useState([
        { 
            sender: 'assistant', 
            text: '👋 Hello! I am your AI Scheduling Agent. I can help organize your academic schedule, track assignment deadlines, and auto-schedule study sessions.\n\nTry prompting me: *"Schedule Physics class on Monday from 10 to 12"* or *"Add Biology assignment due Friday, estimated 4 hours"*.' 
        }
    ]);
    const [inputText, setInputText] = useState("");
    const [chatLoading, setChatLoading] = useState(false);
    
    // Calendar Navigation
    const [currentDate, setCurrentDate] = useState(new Date());
    const [weekOffset, setWeekOffset] = useState(0);
    
    // Form States (Manual Input fallback)
    const [showEventModal, setShowEventModal] = useState(false);
    const [newEvent, setNewEvent] = useState({
        title: "",
        category: "Class",
        start_date: "",
        start_time: "",
        end_time: "",
        description: ""
    });
    
    const [showTaskModal, setShowTaskModal] = useState(false);
    const [newTask, setNewTask] = useState({
        title: "",
        due_date: "",
        due_time: "23:59",
        priority: "Medium",
        difficulty: 3,
        estimated_hours: 2
    });

    const [showSettingsModal, setShowSettingsModal] = useState(false);
    const [editingSettings, setEditingSettings] = useState({});

    const chatEndRef = useRef(null);

    // Scroll to bottom of chat
    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [chatMessages]);

    // Initial Load
    useEffect(() => {
        fetchEvents();
        fetchTasks();
        fetchSettings();
    }, []);

    // API calls
    const fetchEvents = async () => {
        try {
            const res = await fetch("/api/events");
            const data = await res.json();
            setEvents(data);
        } catch (err) {
            console.error("Error fetching events:", err);
        }
    };

    const fetchTasks = async () => {
        try {
            const res = await fetch("/api/tasks");
            const data = await res.json();
            setTasks(data);
        } catch (err) {
            console.error("Error fetching tasks:", err);
        }
    };

    const fetchSettings = async () => {
        try {
            const res = await fetch("/api/settings");
            const data = await res.json();
            setSettings(data);
            setEditingSettings(data);
        } catch (err) {
            console.error("Error fetching settings:", err);
        }
    };

    const handleSendMessage = async (textToSend = inputText) => {
        const text = textToSend.trim();
        if (!text) return;
        
        setChatMessages(prev => [...prev, { sender: 'user', text }]);
        setInputText("");
        setChatLoading(true);

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt: text })
            });
            const data = await response.json();
            
            setChatMessages(prev => [...prev, { sender: 'assistant', text: data.response }]);
            
            // Refresh data since database was updated
            fetchEvents();
            fetchTasks();
        } catch (err) {
            setChatMessages(prev => [...prev, { 
                sender: 'assistant', 
                text: "❌ Oops, I encountered an error executing that request. Please make sure the backend server is running correctly." 
            }]);
        } finally {
            setChatLoading(false);
        }
    };

    const handleQuickAction = (promptText) => {
        handleSendMessage(promptText);
    };

    const handleDeleteEvent = async (id) => {
        if (!confirm("Are you sure you want to delete this event?")) return;
        try {
            await fetch(`/api/events/${id}`, { method: "DELETE" });
            fetchEvents();
        } catch (err) {
            console.error("Error deleting event:", err);
        }
    };

    const handleDeleteTask = async (id) => {
        if (!confirm("Are you sure you want to delete this task? This will also remove any auto-scheduled study sessions associated with it.")) return;
        try {
            await fetch(`/api/tasks/${id}`, { method: "DELETE" });
            fetchTasks();
            fetchEvents(); // Study sessions are events
        } catch (err) {
            console.error("Error deleting task:", err);
        }
    };

    const handleCreateEvent = async (e) => {
        e.preventDefault();
        const startIso = `${newEvent.start_date}T${newEvent.start_time}:00`;
        const endIso = `${newEvent.start_date}T${newEvent.end_time}:00`;
        
        try {
            const res = await fetch("/api/events", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    title: newEvent.title,
                    category: newEvent.category,
                    start_time: startIso,
                    end_time: endIso,
                    description: newEvent.description
                })
            });
            const data = await res.json();
            
            if (data.status === "rescheduled") {
                alert(`⚠️ Conflict resolved! ${data.message}`);
            }
            
            setShowEventModal(false);
            setNewEvent({ title: "", category: "Class", start_date: "", start_time: "", end_time: "", description: "" });
            fetchEvents();
        } catch (err) {
            alert("Error creating event");
        }
    };

    const handleCreateTask = async (e) => {
        e.preventDefault();
        const dueIso = `${newTask.due_date}T${newTask.due_time}:00`;
        
        try {
            await fetch("/api/tasks", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    title: newTask.title,
                    due_date: dueIso,
                    priority: newTask.priority,
                    difficulty: parseInt(newTask.difficulty),
                    estimated_hours: parseFloat(newTask.estimated_hours)
                })
            });
            
            setShowTaskModal(false);
            setNewTask({ title: "", due_date: "", due_time: "23:59", priority: "Medium", difficulty: 3, estimated_hours: 2 });
            fetchTasks();
            fetchEvents(); // Re-fetch to load new study sessions
        } catch (err) {
            alert("Error creating task");
        }
    };

    const handleSaveSettings = async (e) => {
        e.preventDefault();
        try {
            await fetch("/api/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(editingSettings)
            });
            setSettings(editingSettings);
            setShowSettingsModal(false);
        } catch (err) {
            alert("Error saving settings");
        }
    };

    // Calendar Calculations
    const getStartOfWeek = (d) => {
        const date = new Date(d);
        const day = date.getDay();
        const diff = date.getDate() - day + (day === 0 ? -6 : 1); // adjust when day is sunday
        const start = new Date(date.setDate(diff));
        start.setHours(0,0,0,0);
        return start;
    };

    const getWeekDays = () => {
        const monday = getStartOfWeek(new Date(currentDate.getTime() + weekOffset * 7 * 24 * 60 * 60 * 1000));
        const days = [];
        for (let i = 0; i < 7; i++) {
            const nextDay = new Date(monday);
            nextDay.setDate(monday.getDate() + i);
            days.push(nextDay);
        }
        return days;
    };

    const weekDays = getWeekDays();
    const formattedWeekRange = () => {
        const start = weekDays[0];
        const end = weekDays[6];
        const options = { month: 'short', day: 'numeric', year: 'numeric' };
        return `${start.toLocaleDateString(undefined, options)} - ${end.toLocaleDateString(undefined, options)}`;
    };

    const getEventsForDay = (day) => {
        return events.filter(e => {
            const evDate = new Date(e.start_time);
            return evDate.getFullYear() === day.getFullYear() &&
                   evDate.getMonth() === day.getMonth() &&
                   evDate.getDate() === day.getDate();
        }).sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
    };

    const getCategoryStyles = (category) => {
        switch (category) {
            case "Class": return "category-class text-violet-300";
            case "Exam": return "category-exam text-red-300 glow-danger";
            case "Study Session": return "category-study text-cyan-300 glow-primary";
            case "Break": return "category-break text-emerald-300 glow-success";
            case "Personal": return "category-personal text-amber-300";
            default: return "bg-slate-800 border-l-4 border-slate-500 text-slate-300";
        }
    };

    return (
        <div class="flex-grow flex flex-col p-4 md:p-6 lg:p-8 max-w-[1600px] w-full mx-auto relative z-10">
            
            {/* Header Area */}
            <header class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6 md:mb-8 glass-panel p-6 rounded-2xl glow-primary">
                <div class="flex items-center gap-4">
                    <div class="w-12 h-12 rounded-xl bg-gradient-to-tr from-violet-600 to-indigo-600 flex items-center justify-center glow-primary">
                        <i data-lucide="bot" class="w-7 h-7 text-white animate-pulse"></i>
                    </div>
                    <div>
                        <h1 class="text-2xl font-extrabold tracking-tight bg-gradient-to-r from-violet-400 via-indigo-200 to-cyan-300 bg-clip-text text-transparent">
                            Smart Timetable Assistant
                        </h1>
                        <p class="text-xs text-slate-400 mt-1 flex items-center gap-1.5">
                            <span class="w-2 h-2 rounded-full bg-emerald-500 inline-block animate-ping"></span>
                            AI Scheduler Agent • Active & Learning
                        </p>
                    </div>
                </div>
                
                <div class="flex flex-wrap gap-2.5">
                    <button onClick={() => setShowSettingsModal(true)} class="glass-card hover-glow text-slate-200 px-4 py-2 rounded-xl text-sm font-semibold flex items-center gap-2">
                        <i data-lucide="settings" class="w-4 h-4 text-violet-400"></i>
                        Settings
                    </button>
                    <button onClick={() => setShowTaskModal(true)} class="bg-indigo-600/30 hover:bg-indigo-600/50 hover-glow border border-indigo-500/50 text-indigo-200 px-4 py-2 rounded-xl text-sm font-semibold flex items-center gap-2">
                        <i data-lucide="plus-circle" class="w-4 h-4"></i>
                        Add Task
                    </button>
                    <button onClick={() => setShowEventModal(true)} class="bg-violet-600 hover:bg-violet-700 hover-glow text-white px-4 py-2 rounded-xl text-sm font-semibold flex items-center gap-2 glow-primary">
                        <i data-lucide="calendar" class="w-4 h-4"></i>
                        Add Event
                    </button>
                </div>
            </header>

            {/* Main Content Grid */}
            <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-grow items-stretch">
                
                {/* LEFT COLUMN: TASK TRACKER & PREFERENCES (3 cols) */}
                <div class="lg:col-span-3 flex flex-col gap-6">
                    
                    {/* Settings Snapshot */}
                    <div class="glass-panel p-5 rounded-2xl flex flex-col gap-4">
                        <h2 class="text-sm font-extrabold uppercase tracking-widest text-slate-400 flex items-center gap-2">
                            <i data-lucide="clock" class="w-4 h-4 text-indigo-400"></i>
                            Scheduling Profile
                        </h2>
                        <div class="grid grid-cols-2 gap-3 text-xs">
                            <div class="glass-card p-3 rounded-xl border border-slate-800">
                                <span class="text-slate-400 block mb-0.5">Study Target</span>
                                <span class="font-bold text-cyan-300">{settings.study_start} - {settings.study_end}</span>
                            </div>
                            <div class="glass-card p-3 rounded-xl border border-slate-800">
                                <span class="text-slate-400 block mb-0.5">Sleep Hours</span>
                                <span class="font-bold text-violet-400">{settings.sleep_start} - {settings.sleep_end}</span>
                            </div>
                        </div>
                    </div>

                    {/* Task Tracker Kanban list */}
                    <div class="glass-panel p-5 rounded-2xl flex-grow flex flex-col gap-4 max-h-[500px] lg:max-h-none overflow-y-auto">
                        <div class="flex justify-between items-center">
                            <h2 class="text-sm font-extrabold uppercase tracking-widest text-slate-400 flex items-center gap-2">
                                <i data-lucide="check-square" class="w-4 h-4 text-cyan-400"></i>
                                Academic Tasks ({tasks.length})
                            </h2>
                        </div>
                        
                        {tasks.length === 0 ? (
                            <div class="flex-grow flex flex-col items-center justify-center p-6 text-center text-slate-500 border border-dashed border-slate-800 rounded-xl">
                                <i data-lucide="smile" class="w-8 h-8 mb-2 text-slate-600"></i>
                                <span class="text-sm">No tasks added yet. Add one manually or ask the AI assistant.</span>
                            </div>
                        ) : (
                            <div class="flex flex-col gap-3">
                                {tasks.map(task => (
                                    <div key={task.id} class="glass-card p-4 rounded-xl border border-slate-800 hover:border-slate-700 transition flex flex-col gap-2.5 animate-fade-in relative group">
                                        <div class="flex justify-between items-start gap-2">
                                            <span class="font-bold text-slate-200 text-sm leading-snug">{task.title}</span>
                                            <button onClick={() => handleDeleteTask(task.id)} class="text-slate-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition p-1 rounded">
                                                <i data-lucide="trash-2" class="w-4 h-4"></i>
                                            </button>
                                        </div>
                                        
                                        <div class="flex flex-wrap gap-2 text-[10px] items-center mt-1">
                                            <span class={`px-2 py-0.5 rounded-full font-bold ${
                                                task.priority === "High" ? "bg-red-950 text-red-400 border border-red-800/30" :
                                                task.priority === "Medium" ? "bg-amber-950 text-amber-400 border border-amber-800/30" :
                                                "bg-slate-900 text-slate-400 border border-slate-800"
                                            }`}>
                                                {task.priority} Priority
                                            </span>
                                            
                                            <span class="bg-indigo-950/40 text-indigo-300 px-2 py-0.5 rounded-full border border-indigo-800/30 font-semibold">
                                                Diff: {task.difficulty}/5
                                            </span>

                                            <span class="bg-cyan-950/40 text-cyan-300 px-2 py-0.5 rounded-full border border-cyan-800/30 font-semibold">
                                                {task.estimated_hours}h Study
                                            </span>
                                        </div>
                                        
                                        <div class="flex justify-between items-center text-xs text-slate-400 mt-1 border-t border-slate-800/50 pt-2">
                                            <span class="flex items-center gap-1">
                                                <i data-lucide="calendar" class="w-3.5 h-3.5 text-slate-500"></i>
                                                {new Date(task.due_date).toLocaleDateString(undefined, {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'})}
                                            </span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* CENTER COLUMN: INTERACTIVE WEEK CALENDAR BOARD (6 cols) */}
                <div class="lg:col-span-6 flex flex-col gap-4 glass-panel p-5 rounded-2xl">
                    
                    {/* Calendar Control Bar */}
                    <div class="flex justify-between items-center gap-4 pb-4 border-b border-slate-800">
                        <div class="flex items-center gap-2">
                            <button onClick={() => setWeekOffset(0)} class="glass-card hover:bg-slate-800/50 text-slate-300 px-3 py-1.5 rounded-lg text-xs font-semibold">
                                Today
                            </button>
                            <div class="flex items-center bg-slate-900/60 rounded-lg p-0.5 border border-slate-800">
                                <button onClick={() => setWeekOffset(prev => prev - 1)} class="p-1.5 hover:bg-slate-800 rounded-md text-slate-400 hover:text-white">
                                    <i data-lucide="chevron-left" class="w-4 h-4"></i>
                                </button>
                                <button onClick={() => setWeekOffset(prev => prev + 1)} class="p-1.5 hover:bg-slate-800 rounded-md text-slate-400 hover:text-white">
                                    <i data-lucide="chevron-right" class="w-4 h-4"></i>
                                </button>
                            </div>
                        </div>
                        
                        <h2 class="text-sm md:text-base font-bold text-slate-200 text-center">
                            {formattedWeekRange()}
                        </h2>
                        
                        <span class="text-xs text-indigo-400 font-medium hidden md:inline-flex items-center gap-1.5 bg-indigo-950/40 px-2.5 py-1 rounded-full border border-indigo-800/30">
                            <i data-lucide="calendar-days" class="w-3.5 h-3.5"></i>
                            Weekly View
                        </span>
                    </div>

                    {/* Week Agenda Board */}
                    <div class="grid grid-cols-1 md:grid-cols-7 gap-3 mt-2 overflow-y-auto flex-grow max-h-[70vh]">
                        {weekDays.map((day, idx) => {
                            const isToday = new Date().toDateString() === day.toDateString();
                            const dayEvents = getEventsForDay(day);
                            
                            return (
                                <div key={idx} class={`flex flex-col gap-2 p-2 rounded-xl transition ${
                                    isToday ? "bg-violet-950/15 border border-violet-800/30 shadow-[0_0_15px_rgba(139,92,246,0.05)]" : "bg-slate-900/20 border border-slate-900/50"
                                } min-h-[160px]`}>
                                    
                                    {/* Day Header */}
                                    <div class="flex justify-between items-center px-1 pb-1.5 border-b border-slate-800/40">
                                        <span class={`text-[10px] uppercase font-extrabold tracking-widest ${isToday ? "text-violet-400" : "text-slate-500"}`}>
                                            {day.toLocaleDateString(undefined, { weekday: 'short' })}
                                        </span>
                                        <span class={`w-5 h-5 flex items-center justify-center text-xs font-bold rounded-full ${
                                            isToday ? "bg-violet-500 text-white font-extrabold shadow-md shadow-violet-500/30" : "text-slate-300"
                                        }`}>
                                            {day.getDate()}
                                        </span>
                                    </div>
                                    
                                    {/* Day Events Column */}
                                    <div class="flex-grow flex flex-col gap-2 overflow-y-auto max-h-[380px]">
                                        {dayEvents.length === 0 ? (
                                            <span class="text-[10px] text-slate-600 text-center py-4 italic">Free Slot</span>
                                        ) : (
                                            dayEvents.map(event => {
                                                const st = new Date(event.start_time);
                                                const et = new Date(event.end_time);
                                                const timeStr = `${st.toLocaleTimeString(undefined, {hour: 'numeric', minute:'2-digit', hour12: true})} - ${et.toLocaleTimeString(undefined, {hour: 'numeric', minute:'2-digit', hour12: true})}`;
                                                
                                                return (
                                                    <div 
                                                        key={event.id} 
                                                        class={`p-2.5 rounded-lg text-left text-xs ${getCategoryStyles(event.category)} relative group animate-fade-in hover:brightness-110 transition`}
                                                    >
                                                        <div class="flex justify-between items-start gap-1">
                                                            <span class="font-bold tracking-tight text-[11px] leading-tight block mb-0.5">{event.title}</span>
                                                            <button onClick={() => handleDeleteEvent(event.id)} class="text-slate-400 hover:text-red-400 opacity-0 group-hover:opacity-100 transition">
                                                                <i data-lucide="x" class="w-3 h-3"></i>
                                                            </button>
                                                        </div>
                                                        <span class="text-[9px] text-slate-400 block font-medium">{timeStr}</span>
                                                        {event.description && (
                                                            <p class="text-[9px] text-slate-500 mt-1 line-clamp-2 leading-snug border-t border-slate-700/20 pt-1">
                                                                {event.description}
                                                            </p>
                                                        )}
                                                    </div>
                                                );
                                            })
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* RIGHT COLUMN: AI SCHEDULING CONVERSATIONAL AGENT (3 cols) */}
                <div class="lg:col-span-3 flex flex-col glass-panel rounded-2xl overflow-hidden min-h-[500px]">
                    
                    {/* Chat Header */}
                    <div class="bg-slate-900/50 p-4 border-b border-slate-800 flex items-center gap-3.5">
                        <div class="w-8 h-8 rounded-lg bg-indigo-500/20 flex items-center justify-center">
                            <i data-lucide="sparkles" class="w-4.5 h-4.5 text-indigo-400"></i>
                        </div>
                        <div>
                            <h2 class="text-sm font-extrabold text-slate-200">AI Scheduling Assistant</h2>
                            <p class="text-[10px] text-slate-500">Natural language schedule parser</p>
                        </div>
                    </div>

                    {/* Chat Display Box */}
                    <div class="flex-grow overflow-y-auto p-4 flex flex-col gap-3.5 max-h-[360px] lg:max-h-[50vh]">
                        {chatMessages.map((msg, index) => (
                            <div key={index} class={`flex flex-col max-w-[85%] ${msg.sender === 'user' ? 'self-end items-end' : 'self-start items-start'}`}>
                                <span class="text-[9px] text-slate-500 mb-1 px-1">{msg.sender === 'user' ? 'You' : 'AI Assistant'}</span>
                                <div class={`p-3 rounded-xl text-xs leading-relaxed whitespace-pre-line ${
                                    msg.sender === 'user' 
                                        ? 'bg-violet-600 text-white rounded-tr-none shadow-md shadow-violet-600/10' 
                                        : 'bg-slate-900/70 border border-slate-800 text-slate-200 rounded-tl-none'
                                }`}>
                                    {msg.text}
                                </div>
                            </div>
                        ))}
                        {chatLoading && (
                            <div class="self-start items-start flex flex-col max-w-[85%]">
                                <span class="text-[9px] text-slate-500 mb-1 px-1">AI Assistant</span>
                                <div class="bg-slate-900/70 border border-slate-800 text-slate-400 p-3 rounded-xl rounded-tl-none text-xs flex items-center gap-2">
                                    <span class="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce"></span>
                                    <span class="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" style={{animationDelay: '0.2s'}}></span>
                                    <span class="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" style={{animationDelay: '0.4s'}}></span>
                                    Scheduling...
                                </div>
                            </div>
                        )}
                        <div ref={chatEndRef} />
                    </div>

                    {/* Chat Prompt Suggestions */}
                    <div class="p-3 border-t border-slate-800/40 bg-slate-900/10 flex flex-wrap gap-1.5">
                        <button onClick={() => handleQuickAction("Schedule Physics class on Monday from 10 to 12")} class="text-[10px] bg-slate-900 hover:bg-slate-800 text-slate-400 px-2 py-1 rounded-lg border border-slate-800 transition">
                            📅 Add Class
                        </button>
                        <button onClick={() => handleQuickAction("Schedule math exam on Friday at 2 PM")} class="text-[10px] bg-slate-900 hover:bg-slate-800 text-slate-400 px-2 py-1 rounded-lg border border-slate-800 transition">
                            📝 Add Exam
                        </button>
                        <button onClick={() => handleQuickAction("Add Chemistry task due Friday at 5 PM, estimated 4 hours")} class="text-[10px] bg-slate-900 hover:bg-slate-800 text-slate-400 px-2 py-1 rounded-lg border border-slate-800 transition">
                            ✏️ Auto-schedule task
                        </button>
                        <button onClick={() => handleQuickAction("clear calendar")} class="text-[10px] bg-red-950/20 hover:bg-red-950/40 text-red-400 px-2 py-1 rounded-lg border border-red-900/20 transition">
                            🧹 Reset calendar
                        </button>
                    </div>

                    {/* Input Field */}
                    <div class="p-4 border-t border-slate-800 bg-slate-900/30 flex gap-2">
                        <input 
                            type="text" 
                            value={inputText}
                            onChange={(e) => setInputText(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                            placeholder="Type a scheduling command..." 
                            class="flex-grow glass-input px-3.5 py-2.5 rounded-xl text-xs focus:ring-1 focus:ring-violet-500 focus:outline-none"
                            disabled={chatLoading}
                        />
                        <button 
                            onClick={() => handleSendMessage()}
                            class="w-10 h-10 rounded-xl bg-violet-600 hover:bg-violet-700 flex items-center justify-center text-white glow-primary disabled:opacity-50 transition"
                            disabled={chatLoading}
                        >
                            <i data-lucide="send" class="w-4 h-4"></i>
                        </button>
                    </div>

                </div>

            </div>

            {/* MODALS */}
            
            {/* Modal: Add Custom Event */}
            {showEventModal && (
                <div class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-fade-in">
                    <div class="glass-panel w-full max-w-md p-6 rounded-2xl border border-slate-800 flex flex-col gap-4 glow-primary">
                        <div class="flex justify-between items-center pb-2 border-b border-slate-800">
                            <h3 class="text-base font-bold text-slate-100 flex items-center gap-2">
                                <i data-lucide="calendar-plus" class="w-5 h-5 text-violet-400"></i>
                                Schedule Calendar Event
                            </h3>
                            <button onClick={() => setShowEventModal(false)} class="text-slate-400 hover:text-white">
                                <i data-lucide="x" class="w-5 h-5"></i>
                            </button>
                        </div>
                        
                        <form onSubmit={handleCreateEvent} class="flex flex-col gap-4 text-xs">
                            <div class="flex flex-col gap-1.5">
                                <label class="text-slate-400 font-semibold">Event Title</label>
                                <input required type="text" value={newEvent.title} onChange={e => setNewEvent({...newEvent, title: e.target.value})} placeholder="e.g. Math 101 Lecture" class="glass-input px-3 py-2.5 rounded-xl text-xs" />
                            </div>
                            
                            <div class="grid grid-cols-2 gap-3">
                                <div class="flex flex-col gap-1.5">
                                    <label class="text-slate-400 font-semibold">Category</label>
                                    <select value={newEvent.category} onChange={e => setNewEvent({...newEvent, category: e.target.value})} class="glass-input px-3 py-2.5 rounded-xl text-xs bg-slate-900">
                                        <option>Class</option>
                                        <option>Exam</option>
                                        <option>Study Session</option>
                                        <option>Break</option>
                                        <option>Personal</option>
                                    </select>
                                </div>
                                <div class="flex flex-col gap-1.5">
                                    <label class="text-slate-400 font-semibold">Date</label>
                                    <input required type="date" value={newEvent.start_date} onChange={e => setNewEvent({...newEvent, start_date: e.target.value})} class="glass-input px-3 py-2.5 rounded-xl text-xs" />
                                </div>
                            </div>
                            
                            <div class="grid grid-cols-2 gap-3">
                                <div class="flex flex-col gap-1.5">
                                    <label class="text-slate-400 font-semibold">Start Time</label>
                                    <input required type="time" value={newEvent.start_time} onChange={e => setNewEvent({...newEvent, start_time: e.target.value})} class="glass-input px-3 py-2.5 rounded-xl text-xs" />
                                </div>
                                <div class="flex flex-col gap-1.5">
                                    <label class="text-slate-400 font-semibold">End Time</label>
                                    <input required type="time" value={newEvent.end_time} onChange={e => setNewEvent({...newEvent, end_time: e.target.value})} class="glass-input px-3 py-2.5 rounded-xl text-xs" />
                                </div>
                            </div>
                            
                            <div class="flex flex-col gap-1.5">
                                <label class="text-slate-400 font-semibold">Description</label>
                                <textarea value={newEvent.description} onChange={e => setNewEvent({...newEvent, description: e.target.value})} placeholder="Location, room number, or notes" class="glass-input px-3 py-2.5 rounded-xl text-xs h-20 resize-none"></textarea>
                            </div>
                            
                            <button type="submit" class="w-full bg-violet-600 hover:bg-violet-700 text-white font-bold py-3 rounded-xl hover-glow transition mt-2">
                                Save Event
                            </button>
                        </form>
                    </div>
                </div>
            )}

            {/* Modal: Add Task */}
            {showTaskModal && (
                <div class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-fade-in">
                    <div class="glass-panel w-full max-w-md p-6 rounded-2xl border border-slate-800 flex flex-col gap-4 glow-primary">
                        <div class="flex justify-between items-center pb-2 border-b border-slate-800">
                            <h3 class="text-base font-bold text-slate-100 flex items-center gap-2">
                                <i data-lucide="file-plus" class="w-5 h-5 text-cyan-400"></i>
                                Add Academic Task
                            </h3>
                            <button onClick={() => setShowTaskModal(false)} class="text-slate-400 hover:text-white">
                                <i data-lucide="x" class="w-5 h-5"></i>
                            </button>
                        </div>
                        
                        <form onSubmit={handleCreateTask} class="flex flex-col gap-4 text-xs">
                            <div class="flex flex-col gap-1.5">
                                <label class="text-slate-400 font-semibold">Task Title</label>
                                <input required type="text" value={newTask.title} onChange={e => setNewTask({...newTask, title: e.target.value})} placeholder="e.g. Physics Lab Report" class="glass-input px-3 py-2.5 rounded-xl text-xs" />
                            </div>
                            
                            <div class="grid grid-cols-2 gap-3">
                                <div class="flex flex-col gap-1.5">
                                    <label class="text-slate-400 font-semibold">Due Date</label>
                                    <input required type="date" value={newTask.due_date} onChange={e => setNewTask({...newTask, due_date: e.target.value})} class="glass-input px-3 py-2.5 rounded-xl text-xs" />
                                </div>
                                <div class="flex flex-col gap-1.5">
                                    <label class="text-slate-400 font-semibold">Due Time</label>
                                    <input type="time" value={newTask.due_time} onChange={e => setNewTask({...newTask, due_time: e.target.value})} class="glass-input px-3 py-2.5 rounded-xl text-xs" />
                                </div>
                            </div>
                            
                            <div class="grid grid-cols-3 gap-3">
                                <div class="flex flex-col gap-1.5">
                                    <label class="text-slate-400 font-semibold">Priority</label>
                                    <select value={newTask.priority} onChange={e => setNewTask({...newTask, priority: e.target.value})} class="glass-input px-3 py-2.5 rounded-xl text-xs bg-slate-900">
                                        <option>High</option>
                                        <option>Medium</option>
                                        <option>Low</option>
                                    </select>
                                </div>
                                <div class="flex flex-col gap-1.5">
                                    <label class="text-slate-400 font-semibold">Difficulty (1-5)</label>
                                    <input required type="number" min="1" max="5" value={newTask.difficulty} onChange={e => setNewTask({...newTask, difficulty: e.target.value})} class="glass-input px-3 py-2.5 rounded-xl text-xs" />
                                </div>
                                <div class="flex flex-col gap-1.5">
                                    <label class="text-slate-400 font-semibold">Study Est. (Hrs)</label>
                                    <input required type="number" step="0.5" min="0.5" value={newTask.estimated_hours} onChange={e => setNewTask({...newTask, estimated_hours: e.target.value})} class="glass-input px-3 py-2.5 rounded-xl text-xs" />
                                </div>
                            </div>
                            
                            <div class="bg-cyan-950/20 border border-cyan-800/20 p-3 rounded-xl text-[10px] text-cyan-300 leading-normal mt-1 flex items-start gap-2.5">
                                <i data-lucide="info" class="w-4.5 h-4.5 text-cyan-400 flex-shrink-0 mt-0.5"></i>
                                <span><strong>AI Auto-Scheduler Note:</strong> Creating this task will prompt the agent to find the next available slots in your preferred study window and allocate {newTask.estimated_hours} hours of study sessions automatically.</span>
                            </div>

                            <button type="submit" class="w-full bg-cyan-600 hover:bg-cyan-700 text-white font-bold py-3 rounded-xl hover-glow transition mt-2">
                                Add Task & Auto-Schedule
                            </button>
                        </form>
                    </div>
                </div>
            )}

            {/* Modal: Edit Settings */}
            {showSettingsModal && (
                <div class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-fade-in">
                    <div class="glass-panel w-full max-w-sm p-6 rounded-2xl border border-slate-800 flex flex-col gap-4 glow-primary">
                        <div class="flex justify-between items-center pb-2 border-b border-slate-800">
                            <h3 class="text-base font-bold text-slate-100 flex items-center gap-2">
                                <i data-lucide="user-cog" class="w-5 h-5 text-indigo-400"></i>
                                Settings Profile
                            </h3>
                            <button onClick={() => setShowSettingsModal(false)} class="text-slate-400 hover:text-white">
                                <i data-lucide="x" class="w-5 h-5"></i>
                            </button>
                        </div>
                        
                        <form onSubmit={handleSaveSettings} class="flex flex-col gap-4 text-xs">
                            <div class="grid grid-cols-2 gap-3">
                                <div class="flex flex-col gap-1.5">
                                    <label class="text-slate-400 font-semibold">Study Start Time</label>
                                    <input type="time" value={editingSettings.study_start} onChange={e => setEditingSettings({...editingSettings, study_start: e.target.value})} class="glass-input px-3 py-2.5 rounded-xl text-xs" />
                                </div>
                                <div class="flex flex-col gap-1.5">
                                    <label class="text-slate-400 font-semibold">Study End Time</label>
                                    <input type="time" value={editingSettings.study_end} onChange={e => setEditingSettings({...editingSettings, study_end: e.target.value})} class="glass-input px-3 py-2.5 rounded-xl text-xs" />
                                </div>
                            </div>
                            
                            <div class="grid grid-cols-2 gap-3">
                                <div class="flex flex-col gap-1.5">
                                    <label class="text-slate-400 font-semibold">Sleep Starts At</label>
                                    <input type="time" value={editingSettings.sleep_start} onChange={e => setEditingSettings({...editingSettings, sleep_start: e.target.value})} class="glass-input px-3 py-2.5 rounded-xl text-xs" />
                                </div>
                                <div class="flex flex-col gap-1.5">
                                    <label class="text-slate-400 font-semibold">Sleep Ends At</label>
                                    <input type="time" value={editingSettings.sleep_end} onChange={e => setEditingSettings({...editingSettings, sleep_end: e.target.value})} class="glass-input px-3 py-2.5 rounded-xl text-xs" />
                                </div>
                            </div>
                            
                            <div class="flex flex-col gap-1.5">
                                <label class="text-slate-400 font-semibold">Timezone</label>
                                <input type="text" value={editingSettings.timezone} onChange={e => setEditingSettings({...editingSettings, timezone: e.target.value})} class="glass-input px-3 py-2.5 rounded-xl text-xs" />
                            </div>
                            
                            <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 rounded-xl hover-glow transition mt-2">
                                Save Profile Settings
                            </button>
                        </form>
                    </div>
                </div>
            )}
            
            {/* Initialize Lucide icons on React render updates */}
            {useEffect(() => {
                lucide.createIcons();
            })}
        </div>
    );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
