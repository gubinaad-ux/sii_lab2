import tkinter as tk
from tkinter import ttk, messagebox
import re
import os

RULES_FILE = "rules.txt"


class Rule:
    def __init__(self, conditions, c_obj, c_val):
        self.conditions = conditions
        self.c_obj = c_obj
        self.c_val = c_val

    def to_str(self):
        cond = " И ".join(f"{o}={v}" for o, v in self.conditions)
        return f"ЕСЛИ {cond} ТО {self.c_obj}={self.c_val}"

    @staticmethod
    def parse(line):
        line = line.strip()
        if not line or line.startswith("#"):
            return None
        m = re.match(r"^ЕСЛИ\s+(.+?)\s+ТО\s+(.+)$", line, re.IGNORECASE)
        if not m:
            return None
        cond_part = m.group(1).strip()
        concl_part = m.group(2).strip()

        conds = []
        for c in re.split(r"\s+И\s+", cond_part):
            if "=" not in c:
                return None
            o, v = c.split("=", 1)
            conds.append((o.strip(), v.strip()))

        if "=" not in concl_part:
            return None
        co, cv = concl_part.split("=", 1)
        return Rule(conds, co.strip(), cv.strip())


class ExpertSystem:
    def __init__(self):
        self.rules = []

    def load_rules(self, path):
        self.rules = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                r = Rule.parse(line)
                if r:
                    self.rules.append(r)

    def save_rules(self, path):
        with open(path, "w", encoding="utf-8") as f:
            for r in self.rules:
                f.write(r.to_str() + "\n")

    def collect_objects(self):
        values = {}
        for r in self.rules:
            for o, v in r.conditions:
                values.setdefault(o, set()).add(v) #Если ключа o нет, то создаём его со значением set() и возвращает этот пустой set.
            values.setdefault(r.c_obj, set()).add(r.c_val)
        return {o: sorted(v) for o, v in values.items()}

    def input_objects(self):
        result = set()
        for r in self.rules:
            for o, _ in r.conditions:
                result.add(o)
        return sorted(result)

    def target_values(self):
        result = set()
        for r in self.rules:
            if r.c_obj == "рекомендация":
                result.add(r.c_val)
        return sorted(result)

    def _prove(self, facts, obj, val, used_rules, visited, log, depth, missing):
        indent = "    " * depth

        if facts.get(obj) == val:
            log.append(f"{indent}{obj}={val} — уже известно")
            return facts

        if obj in facts:
            log.append(f"{indent}{obj}={val} — противоречие: уже {obj}={facts[obj]}")
            return None

        if (obj, val) in visited:
            log.append(f"{indent}{obj}={val} — уже проверялось, пропускаем")
            return None
        visited = visited | {(obj, val)}

        log.append(f"{indent}Доказываем {obj}={val}")

        tried = False
        for i, rule in enumerate(self.rules):
            if i in used_rules:
                continue
            if rule.c_obj != obj or rule.c_val != val:
                continue
            tried = True

            log.append(f"{indent}  пробуем правило: {rule.to_str()}")
            new_used = used_rules | {i}
            new_facts = dict(facts)
            ok = True
            for co, cv in rule.conditions:
                result = self._prove(new_facts, co, cv,
                                     new_used, visited, log, depth + 2, missing)
                if result is None:
                    log.append(f"{indent}  условие {co}={cv} доказать не удалось")
                    ok = False
                    break
                new_facts = result
            if ok:
                new_facts[obj] = val
                log.append(f"{indent}  {obj}={val} доказано")
                return 

            else:
                log.append(f"{indent}  правило не подошло")

        if tried:
            log.append(f"{indent}  других правил для {obj}={val} нет")

        log.append(f"{indent}{obj}={val} доказать не удалось")
        return None

    def backward_infer(self, facts, target_obj, target_val):
        log = []
        log.append(f"Цель: {target_obj}={target_val}")
        init = ", ".join(f"{o}={v}" for o, v in facts.items()) if facts else "(пусто)"
        log.append(f"Начальные факты: {init}")
        log.append("")

        missing = set()
        result = self._prove(facts, target_obj, target_val,
                             frozenset(), frozenset(), log, depth=0, missing=missing)
        return result, log, missing


class AskDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Не хватает данных")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self.result = None

        ttk.Label(
            self,
            text="Для доказательства цели не хватает данных.\n\n"
                 "Продолжить ввод или завершить программу?",
            justify="center",
        ).pack(padx=30, pady=20)

        btns = ttk.Frame(self)
        btns.pack(padx=30, pady=(0, 20))
        ttk.Button(btns, text="Продолжить ввод",
                   command=self._continue).pack(side="left", padx=6)
        ttk.Button(btns, text="Завершить программу",
                   command=self._quit).pack(side="left", padx=6)

        self.wait_window(self)

    def _continue(self):
        self.result = "continue"
        self.destroy()

    def _quit(self):
        self.result = "quit"
        self.destroy()


class RuleDialog(tk.Toplevel):
    def __init__(self, parent, rule=None):
        super().__init__(parent)
        self.title("Правило")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self.result = None

        ttk.Label(
            self,
            text="Формат: ЕСЛИ объект1=значение1 И объект2=значение2 ТО объект3=значение3",
            justify="center",
        ).pack(padx=20, pady=12)

        self.text = tk.Text(self, width=72, height=4, wrap="word", undo=True)
        self.text.pack(padx=20, pady=5)

        self._menu = tk.Menu(self.text, tearoff=0)
        self._menu.add_command(label="Вырезать",
                               command=lambda: self.text.event_generate("<<Cut>>"))
        self._menu.add_command(label="Копировать",
                               command=lambda: self.text.event_generate("<<Copy>>"))
        self._menu.add_command(label="Вставить",
                               command=lambda: self.text.event_generate("<<Paste>>"))
        self.text.bind("<Button-3>", self._show_menu)

        if rule:
            self.text.insert("1.0", rule.to_str())

        btns = ttk.Frame(self)
        btns.pack(padx=20, pady=12)
        ttk.Button(btns, text="ОК", command=self._ok).pack(side="left", padx=6)
        ttk.Button(btns, text="Отмена", command=self.destroy).pack(side="left", padx=6)

        self.wait_window(self)

    def _show_menu(self, event):
        self.text.focus_set()
        self._menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _ok(self):
        raw = self.text.get("1.0", "end").strip()
        parsed = Rule.parse(raw)
        if not parsed:
            messagebox.showerror(
                "Ошибка",
                "Не удалось разобрать правило.\n"
                "Проверьте формат: ЕСЛИ ... ТО ...",
                parent=self,
            )
            return
        self.result = parsed
        self.destroy()


class RulesEditor(tk.Toplevel):
    def __init__(self, parent, es):
        super().__init__(parent)
        self.title("Редактирование базы правил")
        self.transient(parent)
        self.grab_set()
        self.geometry("920x600")
        self.es = es

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(container, columns=("rule",), show="headings")
        self.tree.heading("rule", text="Правило")
        self.tree.column("rule", width=840, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10, pady=10)
        ttk.Button(btns, text="Дополнить", command=self._add).pack(side="left", padx=3)
        ttk.Button(btns, text="Изменить", command=self._edit).pack(side="left", padx=3)
        ttk.Button(btns, text="Удалить",  command=self._del).pack(side="left", padx=3)
        ttk.Button(btns, text="Закрыть",  command=self.destroy).pack(side="right", padx=3)
        ttk.Button(btns, text="Сохранить в файл",
                   command=self._save).pack(side="right", padx=3)

        self._refresh()
        self.wait_window(self)

    def _refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for idx, r in enumerate(self.es.rules):
            self.tree.insert("", "end", iid=str(idx), values=(r.to_str(),))

    def _add(self):
        dlg = RuleDialog(self)
        if dlg.result:
            self.es.rules.append(dlg.result)
            self._refresh()

    def _edit(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        dlg = RuleDialog(self, self.es.rules[idx])
        if dlg.result:
            self.es.rules[idx] = dlg.result
            self._refresh()

    def _del(self):
        sel = self.tree.selection()
        if not sel:
            return
        if not messagebox.askyesno("Удаление",
                                   "Удалить выбранное правило?", parent=self):
            return
        idx = int(sel[0])
        del self.es.rules[idx]
        self._refresh()

    def _save(self):
        try:
            self.es.save_rules(RULES_FILE)
            messagebox.showinfo("Готово",
                                f"Правила сохранены в {RULES_FILE}",
                                parent=self)
        except Exception as e:
            messagebox.showerror("Ошибка", str(e), parent=self)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Экспертная система (обратный вывод): Что посмотреть вечером?")
        self.geometry("700x720")
        self.resizable(False, False)

        self.es = ExpertSystem()
        self._load_rules()

        self.input_vars = {}
        self.target_var = None
        self.form = None

        self._build_ui()

    def _load_rules(self):
        if os.path.exists(RULES_FILE):
            try:
                self.es.load_rules(RULES_FILE)
            except Exception as e:
                messagebox.showerror("Ошибка",
                                     f"Не удалось загрузить правила:\n{e}")

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=12, pady=(12, 4))
        ttk.Button(top, text="✎  Редактировать базу правил",
                   command=self._open_rules_editor).pack(side="right")

        ttk.Label(self, text="Что посмотреть вечером?",
                  font=("Segoe UI", 14, "bold")).pack(pady=(4, 10))

        self.form = ttk.LabelFrame(self, text=" Заполните то, что знаете ")
        self.form.pack(fill="x", padx=12, pady=6)
        self._rebuild_form()

        ttk.Button(self, text="Доказать",
                   command=self._run).pack(pady=14)

        self.result_var = tk.StringVar(value="Результат: —")
        ttk.Label(self, textvariable=self.result_var,
                  font=("Segoe UI", 13, "bold"),
                  foreground="#0a7").pack(pady=4)

        ttk.Label(self, text="Рабочая память (факты):").pack(
            anchor="w", padx=12, pady=(14, 0))
        self.memory_text = tk.Text(self, height=4, width=70,
                                   state="disabled", font=("Consolas", 10))
        self.memory_text.pack(fill="x", padx=12, pady=(2, 10))

        ttk.Label(self, text="Ход доказательства:").pack(
            anchor="w", padx=12, pady=(6, 0))
        self.proof_text = tk.Text(self, height=14, width=70,
                                  state="disabled", font=("Consolas", 9))
        self.proof_text.pack(fill="x", padx=12, pady=(2, 12))

        self._show_memory({})

    def _rebuild_form(self):
        for w in self.form.winfo_children():
            w.destroy()
        self.input_vars.clear()

        objs = [o for o in self.es.input_objects()
                if o not in ("формат", "рекомендация")]
        all_values = self.es.collect_objects()

        row = 0
        for obj in objs:
            ttk.Label(self.form, text=obj.capitalize() + ":").grid(
                row=row, column=0, sticky="w", padx=12, pady=5)
            var = tk.StringVar()
            cb = ttk.Combobox(self.form, textvariable=var,
                              values=[""] + all_values.get(obj, []),
                              state="readonly", width=30)
            cb.grid(row=row, column=1, sticky="ew", padx=12, pady=5)
            self.input_vars[obj] = var
            row += 1

        ttk.Separator(self.form, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", padx=12, pady=8)
        row += 1

        ttk.Label(self.form, text="Цель (рекомендация):").grid(
            row=row, column=0, sticky="w", padx=12, pady=5)
        self.target_var = tk.StringVar()
        targets = self.es.target_values()
        cb = ttk.Combobox(self.form, textvariable=self.target_var,
                          values=targets, state="readonly", width=30)
        cb.grid(row=row, column=1, sticky="ew", padx=12, pady=5)

        self.form.columnconfigure(1, weight=1)

    def _show_memory(self, facts):
        self.memory_text.config(state="normal")
        self.memory_text.delete("1.0", "end")
        if not facts:
            self.memory_text.insert("end", "(пусто)\n")
        else:
            for o, v in sorted(facts.items()):
                self.memory_text.insert("end", f"{o} = {v}\n")
        self.memory_text.config(state="disabled")

    def _open_rules_editor(self):
        RulesEditor(self, self.es)
        self._rebuild_form()

    def _run(self):
        facts = {}
        for o, var in self.input_vars.items():
            v = var.get()
            if v:
                facts[o] = v

        target = self.target_var.get() if self.target_var else ""
        if not target:
            messagebox.showinfo("Нет цели",
                                "Выберите целевую ситуацию (рекомендацию).")
            return

        result, log, missing = self.es.backward_infer(facts, "рекомендация", target)

        self.proof_text.config(state="normal")
        self.proof_text.delete("1.0", "end")
        self.proof_text.insert("end", "\n".join(log))
        self.proof_text.config(state="disabled")

        if result is not None:
            self._show_memory(result)
            self.result_var.set(f"Цель достижима: {target}")
            return

        self._show_memory(facts)

        if missing:
            dlg = AskDialog(self)
            if dlg.result == "quit":
                self.destroy()
                return
            self.result_var.set(
                f"Не хватает: {', '.join(sorted(missing))}. "
                f"Заполните и нажмите «Доказать» снова."
            )
        else:
            self.result_var.set("Цель недостижима при текущих данных")


if __name__ == "__main__":
    App().mainloop()