#pragma once
#include "task.h"
#include <vector>
#include <string>

class Storage {
public:
    static bool save(const std::vector<Task>& tasks, const std::string& filename);
    static std::vector<Task> load(const std::string& filename);
};
