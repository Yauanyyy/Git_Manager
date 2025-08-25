import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, scrolledtext, filedialog
import subprocess
import threading
import queue
import sys
import re
import os

# 更稳健的跨平台处理（仅在 Windows 下启用隐藏控制台）
CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0

class GitProManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Git Pro Manager v4.3 (增强版)")
        self.root.geometry("1200x800")

        self.command_queue = queue.Queue()
        self.default_branch = "main"
        self.current_repo_path = os.getcwd()

        style = ttk.Style()
        style.configure("TButton", padding=6, relief="flat", font=('Helvetica', 10))
        style.configure("TLabel", padding=5, font=('Helvetica', 10))
        style.configure("Treeview.Heading", font=('Helvetica', 10, 'bold'))
        style.configure("TFrame", padding=10)

        self.create_menu()

        # 使用 PanedWindow 允许左右拖动
        main_pane = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        controls_frame = ttk.LabelFrame(main_pane, text="仓库操作", width=200)
        main_pane.add(controls_frame, weight=0)

        info_area_frame = ttk.Frame(main_pane)
        main_pane.add(info_area_frame, weight=1)
        info_area_frame.rowconfigure(1, weight=1)
        info_area_frame.columnconfigure(0, weight=1)

        # 左侧按钮区
        self.btn_open = ttk.Button(controls_frame, text="📂 打开仓库", command=self.open_repository)
        self.btn_open.pack(fill=tk.X, pady=5)
        separator_open = ttk.Separator(controls_frame, orient='horizontal')
        separator_open.pack(fill='x', pady=10)

        self.btn_clone = ttk.Button(controls_frame, text="🛰️ 克隆仓库", command=self.clone_repository)
        self.btn_clone.pack(fill=tk.X, pady=5)
        separator_clone = ttk.Separator(controls_frame, orient='horizontal')
        separator_clone.pack(fill='x', pady=10)

        self.btn_new = ttk.Button(controls_frame, text="🚀 新建分支", command=self.new_branch)
        self.btn_new.pack(fill=tk.X, pady=5)
        self.btn_save = ttk.Button(controls_frame, text="💾 保存进度", command=self.save_progress)
        self.btn_save.pack(fill=tk.X, pady=5)
        self.btn_finish = ttk.Button(controls_frame, text="🎉 完成分支", command=self.finish_branch)
        self.btn_finish.pack(fill=tk.X, pady=5)
        self.btn_sync = ttk.Button(controls_frame, text="🔄 同步当前分支", command=self.sync_branch)
        self.btn_sync.pack(fill=tk.X, pady=5)
        separator = ttk.Separator(controls_frame, orient='horizontal')
        separator.pack(fill='x', pady=20)
        self.btn_diagnose = ttk.Button(controls_frame, text="🩺 生成诊断报告", command=self.generate_diagnostic_report)
        self.btn_diagnose.pack(fill=tk.X, pady=5)

        # 仓库信息区
        repo_info_frame = ttk.LabelFrame(info_area_frame, text="当前仓库")
        repo_info_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        self.current_repo_label = ttk.Label(
            repo_info_frame,
            text="正在检测...",
            anchor="w",
            wraplength=900,
            font=('Helvetica', 12, 'bold')  # 加大加粗
        )
        self.current_repo_label.pack(fill=tk.X, padx=5, pady=2)

        # 状态区
        status_panel_frame = ttk.LabelFrame(info_area_frame, text="工作区状态 (Git Status)")
        status_panel_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        status_panel_frame.rowconfigure(1, weight=1)
        status_panel_frame.columnconfigure(0, weight=1)

        top_status_frame = ttk.Frame(status_panel_frame)
        top_status_frame.grid(row=0, column=0, sticky="ew", pady=5, padx=5)
        top_status_frame.columnconfigure(1, weight=1)

        ttk.Label(top_status_frame, text="分支:").grid(row=0, column=0, sticky="w")
        self.branch_combobox = ttk.Combobox(top_status_frame, state="readonly", width=40)
        self.branch_combobox.grid(row=0, column=1, sticky="ew", padx=5)
        self.branch_combobox.bind("<<ComboboxSelected>>", self.switch_branch_from_combobox)
        self.btn_refresh_status = ttk.Button(top_status_frame, text="🔄 刷新", command=self.refresh_all_status)
        self.btn_refresh_status.grid(row=0, column=2, sticky="e")

        self.status_tree = ttk.Treeview(status_panel_frame, columns=('Status', 'File'), show='headings')
        self.status_tree.heading('Status', text='状态')
        self.status_tree.heading('File', text='文件路径')
        self.status_tree.column('Status', width=150, anchor='w', stretch=tk.NO)
        self.status_tree.column('File', width=400, anchor='w', stretch=tk.YES)
        self.status_tree.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.status_tree.tag_configure('Modified', foreground='blue')
        self.status_tree.tag_configure('Deleted', foreground='red')
        self.status_tree.tag_configure('Untracked', foreground='green')
        self.status_tree.tag_configure('Renamed', foreground='orange')
        self.status_tree.tag_configure('Staged', foreground='dark green')

        # 日志区（可伸缩）
        log_frame = ttk.LabelFrame(info_area_frame, text="输出日志")
        log_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        info_area_frame.rowconfigure(2, weight=1)  # 允许调整高度
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10, state='disabled')
        self.log_text.grid(row=0, column=0, sticky="nsew")

        self.repo_controls = [
            self.btn_new, self.btn_save, self.btn_finish,
            self.btn_sync, self.btn_diagnose, self.btn_refresh_status, self.branch_combobox
        ]

        self.root.after(100, self.initialize_app)
        self.root.after(100, self.process_queue)

        # 启动时默认打开脚本所在目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.set_current_repo(script_dir)

    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="打开仓库...", command=self.open_repository)
        file_menu.add_command(label="克隆仓库...", command=self.clone_repository)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)

        # 操作菜单（功能 3）
        action_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="操作", menu=action_menu)
        action_menu.add_command(label="📂 打开仓库", command=self.open_repository)
        action_menu.add_command(label="🛰️ 克隆仓库", command=self.clone_repository)
        action_menu.add_separator()
        action_menu.add_command(label="🚀 新建分支", command=self.new_branch)
        action_menu.add_command(label="💾 保存进度", command=self.save_progress)
        action_menu.add_command(label="🎉 完成分支", command=self.finish_branch)
        action_menu.add_command(label="🔄 同步当前分支", command=self.sync_branch)
        action_menu.add_separator()
        action_menu.add_command(label="🩺 生成诊断报告", command=self.generate_diagnostic_report)
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="打开仓库...", command=self.open_repository)
        file_menu.add_command(label="克隆仓库...", command=self.clone_repository)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)

    def set_current_repo(self, path):
        self.current_repo_path = path
        self.current_repo_label.config(text=f"当前仓库路径: {self.current_repo_path}")
        self.initialize_app()
    
    def open_repository(self):
        repo_path = filedialog.askdirectory(title="请选择一个 Git 仓库文件夹")
        if not repo_path:
            return
        # 额外健壮性：检查是否为 git 仓库
        if not os.path.isdir(os.path.join(repo_path, '.git')):
            if not messagebox.askyesno("提示", "此目录下未发现 .git，仍要尝试打开并检测吗？"):
                return
        self.set_current_repo(repo_path)

    def clone_repository(self):
        repo_url = simpledialog.askstring("克隆仓库", "请输入远程仓库的 URL (HTTPS 或 SSH):")
        if not repo_url:
            return
        target_dir = filedialog.askdirectory(title="请选择一个文件夹来存放克隆的仓库")
        if not target_dir:
            self.log_message("克隆操作已取消：未选择目标目录。\n", "INFO")
            return
        repo_name = repo_url.split('/')[-1].replace('.git', '')
        final_path = os.path.join(target_dir, repo_name)
        if os.path.exists(final_path) and os.listdir(final_path):
            if not messagebox.askyesno("警告", f"目标目录已存在且非空:\n{final_path}\n仍然尝试克隆到此目录吗？可能会失败。"):
                return
        self.log_message(f"准备克隆 '{repo_url}' 到 '{final_path}'...\n", "INFO")
        self._set_controls_enabled(False)
        def clone_task():
            command = ["git", "clone", repo_url, final_path]
            self.command_queue.put((self.log_message, (f"▶️ 正在执行: {' '.join(command)}\n", "INFO")))
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', creationflags=CREATE_NO_WINDOW)
            for line in iter(process.stdout.readline, ''):
                self.command_queue.put((self.log_message, (line,)))
            process.wait()
            if process.returncode == 0:
                self.command_queue.put((self.log_message, ("\n✅ 克隆成功！\n", "SUCCESS")))
                if messagebox.askyesno("成功", f"仓库已成功克隆到:\n{final_path}\n\n是否立即切换到该仓库进行管理？"):
                    self.command_queue.put((self.set_current_repo, (final_path,)))
                else:
                    self.command_queue.put((self._set_controls_enabled, (True,)))
            else:
                self.command_queue.put((self.log_message, (f"\n❌ 克隆失败，退出代码 {process.returncode}\n", "ERROR")))
                self.command_queue.put((self._set_controls_enabled, (True,)))
        threading.Thread(target=clone_task, daemon=True).start()

    def initialize_app(self):
        self.log_message(f"正在检查目录: {self.current_repo_path}...\n", "INFO")
        self._set_repo_controls_enabled(False)
        def on_check_done(result):
            is_repo = result and result['returncode'] == 0 and result['stdout'].strip() == 'true'
            if is_repo:
                self.log_message("检测到 Git 仓库。正在获取状态...\n", "SUCCESS")
                self.run_git_command(["git", "symbolic-ref", "refs/remotes/origin/HEAD"], on_done=self._on_default_branch_fetched, log_command=False)
            else:
                self.log_message("当前目录不是一个 Git 仓库。\n", "INFO")
                self.status_tree.delete(*self.status_tree.get_children())
                self.status_tree.insert('', 'end', values=('⚠️', '不是一个 Git 仓库。请从“文件”菜单打开或克隆。'))
                self.branch_combobox.set('')
                self.branch_combobox['values'] = []
                self._set_repo_controls_enabled(False)
        self.run_git_command(["git", "rev-parse", "--is-inside-work-tree"], on_done=on_check_done, log_command=False)

    def _on_default_branch_fetched(self, result):
        if result and result['returncode'] == 0:
            self.default_branch = result['stdout'].strip().split('/')[-1]
            self.log_message(f"检测到默认分支为: {self.default_branch}\n", "INFO")
        else:
            self.log_message(f"无法检测到默认分支，将回退到 'main'。\n", "INFO")
            self.default_branch = "main"
        self.refresh_all_status()
        self._set_repo_controls_enabled(True)

    def _set_repo_controls_enabled(self, enabled: bool):
        state = 'normal' if enabled else 'disabled'
        for control in self.repo_controls:
            try:
                if isinstance(control, ttk.Combobox):
                    # Combobox: disabled 状态下避免 set() 触发 TclError
                    control.config(state='readonly' if enabled else 'disabled')
                else:
                    control.config(state=state)
            except tk.TclError:
                pass
        self.root.update_idletasks()

    def _set_controls_enabled(self, enabled: bool):
        self._set_repo_controls_enabled(enabled)
        self.btn_clone.config(state='normal' if enabled else 'disabled')

    def refresh_all_status(self, on_done=None):
        self._set_controls_enabled(False)
        self.refresh_tasks_pending = 2
        def _check_refresh_done():
            self.refresh_tasks_pending -= 1
            if self.refresh_tasks_pending <= 0:
                self._set_controls_enabled(True)
                if on_done:
                    on_done()
        self.update_branches(on_done=_check_refresh_done)
        self.update_status_files(on_done=_check_refresh_done)

    def update_branches(self, on_done=None):
        def on_branches_fetched(result):
            if not result or result['returncode'] != 0:
                self.log_message("获取分支时出错。", "ERROR")
                if on_done:
                    on_done()
                return
            output = result['stdout']
            branches = set()
            for line in output.splitlines():
                line = line.strip()
                if '->' in line or not line:
                    continue
                if line.startswith('*'):
                    line = line[1:].strip()
                if line.startswith('remotes/origin/'):
                    line = line[len('remotes/origin/'):]
                branches.add(line)
            self.run_git_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], on_done=lambda res: on_current_branch_fetched(res, sorted(list(branches))), log_command=False)
        def on_current_branch_fetched(result, sorted_branches):
            if result and result['returncode'] == 0:
                current_branch = result['stdout'].strip()
                self.branch_combobox['values'] = sorted_branches
                if current_branch in sorted_branches:
                    self.branch_combobox.set(current_branch)
            else:
                self.log_message("获取当前分支时出错。", "ERROR")
            if on_done:
                on_done()
        self.run_git_command(["git", "branch", "-a"], on_done=on_branches_fetched, log_command=False)

    def update_status_files(self, on_done=None):
        def on_status_done(result):
            self.status_tree.delete(*self.status_tree.get_children())
            if result and result['returncode'] == 0:
                output = result['stdout']
                lines = output.splitlines()
                if not lines:
                    self.status_tree.insert('', 'end', values=('✅ 干净', '工作区是干净的'))
                status_map = {'M': '已修改', 'D': '已删除', 'A': '已暂存', 'R': '已重命名', 'C': '已复制', 'U': '未合并', '??': '未跟踪'}
                for line in lines:
                    # 支持 1~2 位状态位（porcelain v1 有时首位为空格）
                    match = re.match(r'(.{1,2})\s+(.*)', line)
                    if not match:
                        continue
                    code, path = match.groups()
                    # 规范化 code 长度
                    if len(code) == 1:
                        code = ' ' + code
                    index_status, worktree_status = code[0], code[1]
                    status_text = f"[{code.strip()}] "
                    tag = ''
                    if index_status == '?' and worktree_status == '?':
                        status_text += status_map.get('??', '未跟踪'); tag = 'Untracked'
                    elif index_status == 'R':
                        status_text += status_map.get('R', '已重命名'); tag = 'Renamed'
                    elif index_status == 'D' or worktree_status == 'D':
                        status_text += status_map.get('D', '已删除'); tag = 'Deleted'
                    elif index_status == 'M' or worktree_status == 'M':
                        status_text += status_map.get('M', '已修改'); tag = 'Modified'
                    elif index_status == 'A':
                        status_text += status_map.get('A', '已暂存'); tag = 'Staged'
                    else:
                        status_text += "未知"
                    self.status_tree.insert('', 'end', values=(status_text, path), tags=(tag,))
            if on_done:
                on_done()
        self.run_git_command(["git", "status", "--porcelain=v1"], on_done=on_status_done, log_command=False)

    def switch_branch_from_combobox(self, event=None):
        target_branch = self.branch_combobox.get()
        if not target_branch:
            return
        def on_get_current_branch(result):
            if result and result['returncode'] == 0:
                current_branch = result['stdout'].strip()
                if target_branch != current_branch:
                    if messagebox.askyesno("确认切换", f"您确定要切换到分支 '{target_branch}' 吗？\n请确保您当前的工作已保存。"):
                        self._set_controls_enabled(False)
                        self.run_git_command(["git", "switch", target_branch], on_done=lambda switch_res: self.run_git_command(["git", "pull", "--ff-only"], on_done=lambda pull_res: self.refresh_all_status()) if switch_res and switch_res['returncode'] == 0 else self.refresh_all_status())
                    else:
                        # 复原选择
                        self.branch_combobox.set(current_branch)
            else:
                self.log_message("无法确定当前分支以防止切换。", "ERROR")
        self.run_git_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], on_done=on_get_current_branch, log_command=False)

    def run_git_command(self, command, on_done=None, log_command=True):
        def task():
            try:
                if log_command:
                    self.command_queue.put((self.log_message, (f"▶️ 在 {os.path.basename(self.current_repo_path)} 中执行: {' '.join(command)}\n", "INFO")))
                process = subprocess.Popen(command, cwd=self.current_repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', creationflags=CREATE_NO_WINDOW)
                stdout, stderr = process.communicate()
                result_bundle = {'stdout': stdout, 'stderr': stderr, 'returncode': process.returncode}
                if log_command:
                    if stdout:
                        self.command_queue.put((self.log_message, (stdout,)))
                    if stderr:
                        log_tag = "ERROR" if process.returncode != 0 else "INFO"
                        self.command_queue.put((self.log_message, (f"[{log_tag.upper()} from stderr]\n{stderr}", log_tag)))
                    if process.returncode == 0:
                        self.command_queue.put((self.log_message, ("\n✅ 命令成功！\n", "SUCCESS")))
                    else:
                        self.command_queue.put((self.log_message, (f"\n❌ 命令失败，退出代码 {process.returncode}\n", "ERROR")))
                if on_done:
                    self.command_queue.put((on_done, result_bundle))
            except Exception as e:
                error_msg = f"❌ 执行命令时发生异常: {e}"
                self.command_queue.put((self.log_message, (error_msg, "ERROR")))
                if on_done:
                    self.command_queue.put((on_done, {'stdout': '', 'stderr': str(e), 'returncode': -1}))
        threading.Thread(target=task, daemon=True).start()

    def process_queue(self):
        try:
            callback, args = self.command_queue.get(block=False)
            try:
                if isinstance(args, tuple):
                    callback(*args)
                else:
                    callback(args)
            except Exception as e:
                print(f"执行回调 {callback.__name__} 时出错: {e}")
                try:
                    self.log_message(f"严重：回调 '{callback.__name__}' 中出错: {e}", "ERROR")
                except Exception as log_e:
                    print(f"甚至无法记录回调错误: {log_e}")
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)

    def log_message(self, message, tag=None):
        self.log_text.config(state='normal')
        # 更安全的日志裁剪：保留最后 max_lines 行
        max_lines = 1000
        try:
            total_lines = int(self.log_text.index('end-1c').split('.')[0])
            if total_lines > max_lines:
                self.log_text.delete('1.0', f'end-{max_lines}l')
        except Exception:
            pass
        self.log_text.insert(tk.END, message, tag)
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
    
    def new_branch(self):
        branch_name = simpledialog.askstring("新建分支", "请输入新分支的名称:")
        if branch_name:
            self._set_controls_enabled(False)
            def on_switch(result):
                if result and result['returncode'] == 0:
                    self.run_git_command(["git", "push", "-u", "origin", branch_name], on_done=lambda res: self.refresh_all_status())
                else:
                    self.refresh_all_status()
            self.run_git_command(["git", "switch", "-c", branch_name], on_done=on_switch)

    def save_progress(self):
        self.refresh_all_status(on_done=self._save_progress_step2)

    def _save_progress_step2(self):
        is_clean = False
        children = self.status_tree.get_children()
        if children:
            first_item = self.status_tree.item(children[0])
            if '✅' in first_item['values'][0]:
                is_clean = True
        if is_clean:
            messagebox.showinfo("信息", "工作区是干净的。无需保存。")
            return
        commit_message = simpledialog.askstring("保存进度", "为此次保存输入提交信息:")
        if commit_message:
            self._set_controls_enabled(False)
            def on_add(result):
                if result and result['returncode'] == 0:
                    self.run_git_command(["git", "commit", "-m", commit_message], on_done=on_commit)
                else:
                    self.refresh_all_status()
            def on_commit(result):
                if result and result['returncode'] == 0:
                    self.run_git_command(["git", "push"], on_done=lambda res: self.refresh_all_status())
                else:
                    self.refresh_all_status()
            self.run_git_command(["git", "add", "."], on_done=on_add)

    def sync_branch(self):
        self._set_controls_enabled(False)
        self.run_git_command(["git", "pull"], on_done=lambda result: self.refresh_all_status())

    def finish_branch(self):
        current_branch = self.branch_combobox.get()
        if current_branch == self.default_branch:
            messagebox.showerror("错误", f"不能在默认分支 ('{self.default_branch}') 上执行 '完成' 操作！")
            return
        if messagebox.askyesno("确认完成", f"这将会把 '{current_branch}' 合并到 '{self.default_branch}'。\n您确定要继续吗？"):
            self._set_controls_enabled(False)
            def step1_add(result=None):
                self.run_git_command(["git", "add", "."], on_done=step2_commit)
            def step2_commit(result):
                # 允许 commit 无变更时继续（returncode 1 常见于 nothing to commit）
                proceed = (result is None) or (result.get('returncode') in (0, 1))
                if proceed:
                    self.run_git_command(["git", "switch", self.default_branch], on_done=step3_pull_main)
                else:
                    self.refresh_all_status()
            def step3_pull_main(result=None):
                if result and result['returncode'] == 0:
                    self.run_git_command(["git", "pull"], on_done=step4_merge)
                else:
                    self.refresh_all_status()
            def step4_merge(result):
                if result and result['returncode'] == 0:
                    self.run_git_command(["git", "merge", "--no-ff", current_branch], on_done=step5_push_main)
                else:
                    self.refresh_all_status()
            def step5_push_main(result):
                if result and result['returncode'] == 0:
                    self.run_git_command(["git", "push"], on_done=step6_ask_delete)
                else:
                    self.refresh_all_status()
            def step6_ask_delete(result):
                if result and result['returncode'] == 0:
                    if messagebox.askyesno("清理", f"合并成功！是否删除本地和远程分支 '{current_branch}'？"):
                        self.run_git_command(["git", "push", "origin", "--delete", current_branch], on_done=lambda res: self.run_git_command(["git", "branch", "-d", current_branch], on_done=lambda final_res: self.refresh_all_status()))
                    else:
                        self.refresh_all_status()
                else:
                    self.refresh_all_status()
            step1_add()

    def generate_diagnostic_report(self):
        self._set_controls_enabled(False)
        report_window = tk.Toplevel(self.root)
        report_window.title("诊断报告"); report_window.geometry("700x500")
        report_text = scrolledtext.ScrolledText(report_window, wrap=tk.WORD, font=('Courier', 10))
        report_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        report_text.insert(tk.END, "正在生成诊断报告，请稍候...\n\n"); report_text.config(state='disabled')
        self.report_parts = {}
        report_order = ['分支图', '分支列表', '当前状态']
        def add_to_report(part_name, command_str, result):
            if result:
                report = f"--- {part_name} ---\n$ {command_str}\n" + result.get('stdout', '')
                if result.get('stderr'):
                    report += f"\n[标准错误输出]\n{result['stderr']}"
                report += "\n\n"
            else:
                report = f"--- {part_name} ---\n$ {command_str}\n[命令执行失败]\n\n"
            self.report_parts[part_name] = report
            if len(self.report_parts) == len(report_order):
                report_text.config(state='normal')
                report_text.delete('1.0', tk.END)
                for part in report_order:
                    report_text.insert(tk.END, self.report_parts.get(part, ''))
                report_text.config(state='disabled')
                messagebox.showinfo("完成", "诊断报告已生成！", parent=report_window)
                self._set_controls_enabled(True)
        commands = {
            '分支图': ["git", "log", "--graph", "--all", "--decorate", "--oneline", "--abbrev-commit"],
            '分支列表': ["git", "branch", "-avv"],
            '当前状态': ["git", "status"],
        }
        for name, cmd in commands.items():
            self.run_git_command(cmd, on_done=lambda result, n=name, c=cmd: add_to_report(n, ' '.join(c), result), log_command=False)

if __name__ == "__main__":
    root = tk.Tk()
    app = GitProManager(root)
    root.mainloop()
