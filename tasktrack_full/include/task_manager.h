#pragma once
#include "task.h"
#include <vector>
#include <string>

class TaskManager {
public:
    bool addTask(const std::string& title,
                 const std::string& description,
                 int priority,
                 const std::string& dueDate);

    bool deleteTask(int id);
    bool markDone(int id);
    bool markUndone(int id);

    Task* findTask(int id);

    std::vector<Task> getAll() const;

    int nextId();

private:
    std::vector<Task> tasks;
};
